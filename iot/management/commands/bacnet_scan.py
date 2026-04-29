"""
Management command para escanear dispositivos BACnet en la red.
Usa BAC0 para enviar un broadcast WhoIs y descubrir controladores.

Uso:
    python manage.py bacnet_scan --ip 10.21.1.132/24
    python manage.py bacnet_scan --ip 10.21.1.132/24 --save --gateway-id 1
"""
import asyncio
import time
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Escanea la red BACnet/IP para descubrir dispositivos (WhoIs broadcast)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--ip',
            type=str,
            help='IP local con mascara CIDR para el socket BACnet. Ej: 10.21.1.132/24',
            required=True,
        )
        parser.add_argument(
            '--save',
            action='store_true',
            help='Guardar los dispositivos encontrados en la base de datos',
        )
        parser.add_argument(
            '--gateway-id',
            type=int,
            help='ID del BACnetGateway al que asociar los dispositivos (requerido con --save)',
            default=None,
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=10,
            help='Segundos a esperar por respuestas WhoIs (default: 10)',
        )
        parser.add_argument(
            '--target',
            type=str,
            help='IP especifica a la que enviar un WhoIs Unicast (ej: 10.40.193.100)',
            default=None,
        )
        parser.add_argument(
            '--sweep',
            type=str,
            help='Rango de IPs para barrido Unicast (ej: 10.40.50.1-254 o 10.40.50.0/24)',
            default=None,
        )
        parser.add_argument(
            '--bbmd',
            type=str,
            help='IP del BBMD para registro como Foreign Device (ej: 10.40.193.100)',
            default=None,
        )

    def handle(self, *args, **options):
        ip = options['ip']
        save = options['save']
        gateway_id = options['gateway_id']
        timeout = options['timeout']
        target = options['target']
        sweep = options['sweep']
        bbmd = options['bbmd']

        if save and not gateway_id:
            self.stderr.write(self.style.ERROR(
                'Debes especificar --gateway-id cuando usas --save'
            ))
            return

        self.stdout.write(self.style.WARNING(
            f'\n[SCAN] Iniciando escaneo BACnet en {ip} (timeout: {timeout}s)...\n'
        ))

        # BAC0 necesita un event loop async; lo ejecutamos dentro de asyncio.run()
        try:
            results = asyncio.run(self._do_scan(ip, timeout, target, sweep, bbmd))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'\n[ERROR] Error durante el escaneo: {e}'))
            import traceback
            traceback.print_exc()
            return

        if results:
            self.stdout.write(self.style.SUCCESS(
                f'\n[OK] Encontrados {len(results)} dispositivo(s):\n'
            ))
            for dev in results:
                self.stdout.write(
                    f'  [DEVICE] {dev["name"]}\n'
                    f'     Device ID: {dev["device_id"]}\n'
                    f'     Direccion: {dev["address"]}\n'
                    f'     Vendor:    {dev["vendor"]}\n'
                )
            if save:
                self._save_devices(results, gateway_id)
        else:
            self.stdout.write(self.style.WARNING(
                '[WARN] No se encontraron dispositivos.\n'
                '   Verifica:\n'
                '   1. La IP y mascara sean correctas (ej: 10.21.1.132/24)\n'
                '   2. La VPN este activa y permita trafico UDP 47808\n'
                '   3. Los controladores esten encendidos y en la misma subred\n'
            ))

    async def _do_scan(self, ip, timeout, target=None, sweep=None, bbmd=None):
        """Ejecuta el escaneo BACnet dentro de un contexto async."""
        import BAC0

        self.stdout.write('[SCAN] Inicializando BAC0 (async)...')
        
        # Configurar argumentos para BAC0.lite
        bacnet_args = {'ip': ip}
        if bbmd:
            self.stdout.write(f'[SCAN] Registrando como Foreign Device en BBMD: {bbmd}')
            bacnet_args['bbmdAddress'] = bbmd
            bacnet_args['bbmdTTL'] = 60
            
        bacnet = BAC0.lite(**bacnet_args)

        if target:
            self.stdout.write(f'[SCAN] Enviando WhoIs Unicast a {target}...')
            await bacnet.who_is(address=target)
        elif sweep:
            self.stdout.write(f'[SCAN] Iniciando barrido Unicast en {sweep}...')
            # Generar lista de IPs
            ips = []
            if '/' in sweep:
                import ipaddress
                ips = [str(ip) for ip in ipaddress.IPv4Network(sweep)]
            elif '-' in sweep:
                parts = sweep.split('.')
                range_parts = parts[-1].split('-')
                base_ip = '.'.join(parts[:-1])
                start = int(range_parts[0])
                end = int(range_parts[1])
                ips = [f"{base_ip}.{i}" for i in range(start, end + 1)]
            
            self.stdout.write(f'[SCAN] Enviando WhoIs a {len(ips)} direcciones...')
            # Enviar ráfagas
            tasks = []
            for target_ip in ips:
                try:
                    # Usamos create_task para disparar sin bloquear el bucle principal
                    tasks.append(asyncio.create_task(bacnet.who_is(address=target_ip)))
                    if len(tasks) % 20 == 0:
                        await asyncio.sleep(0.05)
                except:
                    pass
            
            # Esperar a que se envíen todas
            await asyncio.gather(*tasks, return_exceptions=True)
            self.stdout.write(f'[SCAN] Rafaga enviada. Esperando {timeout}s por respuestas...')
        else:
            self.stdout.write('[SCAN] Enviando WhoIs broadcast...')
            await bacnet.who_is()
            
        # Durante la espera, podemos ir monitoreando si aparecen dispositivos
        start_wait = time.time()
        found_so_far = 0
        while time.time() - start_wait < timeout:
            await asyncio.sleep(2)
            devices = bacnet.devices
            if asyncio.iscoroutine(devices):
                devices = await devices
            
            current_count = len(devices) if devices else 0
            if current_count > found_so_far:
                self.stdout.write(f'[SCAN] ...encontrados {current_count} dispositivos hasta ahora...')
                found_so_far = current_count

        # Recuperar lista final
        devices = bacnet.devices
        if asyncio.iscoroutine(devices):
            devices = await devices
            
        results = []

        if devices:
            for device_info in devices:
                # Intentar extraer info de ruteo si existe
                # (IP:Port Net Station)
                addr_str = 'N/A'
                try:
                    if hasattr(device_info, 'address'):
                        addr_str = str(device_info.address)
                    elif isinstance(device_info, tuple) and len(device_info) > 2:
                        addr_str = str(device_info[2])
                except: pass

                if isinstance(device_info, tuple):
                    name = device_info[0] if len(device_info) > 0 else 'Desconocido'
                    dev_id = device_info[1] if len(device_info) > 1 else 0
                    vendor = device_info[3] if len(device_info) > 3 else 'N/A'
                else:
                    name = getattr(device_info, 'name', str(device_info))
                    dev_id = getattr(device_info, 'device_id', 0)
                    vendor = getattr(device_info, 'vendor', 'N/A')

                results.append({
                    'name': str(name),
                    'device_id': int(dev_id) if dev_id else 0,
                    'address': addr_str,
                    'vendor': str(vendor),
                })

        bacnet.disconnect()
        return results

    def _save_devices(self, results, gateway_id):
        from iot.models import BACnetGateway, BACnetDevice

        try:
            gateway = BACnetGateway.objects.get(pk=gateway_id)
        except BACnetGateway.DoesNotExist:
            self.stderr.write(self.style.ERROR(
                f'No existe un Gateway con ID {gateway_id}'
            ))
            return

        created_count = 0
        updated_count = 0

        for dev in results:
            obj, created = BACnetDevice.objects.update_or_create(
                device_id=dev['device_id'],
                defaults={
                    'gateway': gateway,
                    'name': dev['name'],
                    'address': dev['address'],
                    'vendor': dev['vendor'],
                    'is_online': True,
                }
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        gateway.last_sync = timezone.now()
        gateway.save()

        self.stdout.write(self.style.SUCCESS(
            f'\n[SAVED] Guardados en Gateway "{gateway.nombre}":\n'
            f'   {created_count} nuevos, {updated_count} actualizados\n'
        ))
