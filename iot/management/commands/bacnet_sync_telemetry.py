import asyncio
from django.core.management.base import BaseCommand
from iot.models import BACnetPoint, Telemetry
from django.utils import timezone
from asgiref.sync import sync_to_async
import BAC0

class Command(BaseCommand):
    help = 'Sincroniza la telemetria de todos los puntos BACnet registrados'

    @sync_to_async
    def _get_points(self):
        return list(BACnetPoint.objects.all().select_related('device'))

    @sync_to_async
    def _save_telemetry(self, point, value):
        return Telemetry.objects.create(point=point, value=float(value))

    async def _sync_points(self):
        points = await self._get_points()
        if not points:
            self.stdout.write('No hay puntos registrados para sincronizar.')
            return

        bbmd_ip = "10.40.193.100"
        ip_local = "10.21.1.132/24"
        
        self.stdout.write(f'[SYNC] Conectando a BBMD {bbmd_ip}...')
        try:
            bacnet = BAC0.lite(ip=ip_local, bbmdAddress=bbmd_ip, bbmdTTL=60)
            await asyncio.sleep(2)
            
            for p in points:
                try:
                    address = f"{p.device.address} {p.object_type} {p.instance} presentValue"
                    self.stdout.write(f'  [READ] {p.device.name} -> {p.name}... ')
                    
                    value = await asyncio.wait_for(bacnet.read(address), timeout=3.0)
                    
                    # Guardar telemetria asincronamente
                    await self._save_telemetry(p, value)
                    self.stdout.write(self.style.SUCCESS(f'OK: {value}'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'ERROR: {e}'))
            
            bacnet.disconnect()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error de conexion BACnet: {e}'))

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING(f'\n[SYNC] Iniciando sincronizacion de telemetria @ {timezone.now()}\n'))
        asyncio.run(self._sync_points())
        self.stdout.write(self.style.SUCCESS('\n[FIN] Sincronizacion completada.'))
