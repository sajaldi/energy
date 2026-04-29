import asyncio
from django.core.management.base import BaseCommand
from iot.models import BACnetDevice, BACnetSchedule
from django.utils import timezone
from asgiref.sync import sync_to_async
import BAC0

class Command(BaseCommand):
    help = 'Sincroniza los horarios (schedules) de los controladores BACnet'

    @sync_to_async
    def _get_active_devices(self):
        return list(BACnetDevice.objects.filter(is_online=True))

    @sync_to_async
    def _save_schedule(self, device, inst, name, weekly_json, p_val):
        return BACnetSchedule.objects.update_or_create(
            device=device,
            instance=inst,
            defaults={
                'name': name,
                'weekly_schedule': weekly_json,
                'present_value': bool(p_val)
            }
        )

    async def _sync_schedules(self):
        devices = await self._get_active_devices()
        if not devices:
            self.stdout.write('No hay dispositivos online para sincronizar horarios.')
            return

        bbmd_ip = "10.40.193.100"
        ip_local = "10.21.1.132/24"
        
        self.stdout.write(f'[SYNC] Conectando a BBMD {bbmd_ip} para horarios...')
        try:
            bacnet = BAC0.lite(ip=ip_local, bbmdAddress=bbmd_ip, bbmdTTL=60)
            await asyncio.sleep(2)
            
            # Por ahora sincronizamos los horarios clave del dispositivo 11000
            # que es el que sabemos que tiene horarios importantes
            for dev in devices:
                if dev.device_id != 11000: continue # Foco en el T2-N1 por ahora
                
                # Instancias de horarios interesantes que descubrimos
                target_instances = [2, 30, 31, 34] 
                
                for inst in target_instances:
                    try:
                        self.stdout.write(f'  [READ] {dev.name} -> Schedule {inst}... ')
                        
                        name = await asyncio.wait_for(bacnet.read(f"{dev.address} schedule {inst} objectName"), timeout=3.0)
                        weekly = await asyncio.wait_for(bacnet.read(f"{dev.address} schedule {inst} weeklySchedule"), timeout=5.0)
                        p_val = await asyncio.wait_for(bacnet.read(f"{dev.address} schedule {inst} presentValue"), timeout=2.0)
                        
                        # Convertir weekly a un formato JSON serializable
                        weekly_data = []
                        for daily_obj in weekly:
                            day_events = []
                            if hasattr(daily_obj, 'daySchedule'):
                                for event in daily_obj.daySchedule:
                                    t = event.time
                                    v = event.value
                                    val = v.value if hasattr(v, 'value') else v
                                    day_events.append({
                                        'time': str(t)[:5], # Tomamos HH:MM
                                        'value': 1 if val == 1 else 0
                                    })
                            weekly_data.append(day_events)
                        
                        await self._save_schedule(dev, inst, name, weekly_data, p_val)
                        self.stdout.write(self.style.SUCCESS('OK'))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'ERROR: {e}'))
            
            bacnet.disconnect()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error BACnet: {e}'))

    def handle(self, *args, **options):
        asyncio.run(self._sync_schedules())
