from django.core.management.base import BaseCommand
from iot.models import BACnetGateway, BACnetDevice
from django.utils import timezone

class Command(BaseCommand):
    help = 'Provisiona manualmente los dispositivos BACnet desde las capturas de pantalla'

    def handle(self, *args, **options):
        # 1. Asegurar que existe el Gateway
        # Usamos el 10.40.193.100 como gateway principal ya que es el BBMD
        gateway, created = BACnetGateway.objects.update_or_create(
            id=1,
            defaults={
                'nombre': 'Gateway Principal (BBMD)',
                'ip_address': '10.40.193.100',
                'is_active': True
            }
        )
        
        devices_data = [
            {'id': 16000, 'ip': '10.40.75.30', 'name': 'VENTILACION-S0'},
            {'id': 100000, 'ip': '10.40.75.33', 'name': 'CUARTO-DE-BOMBA'},
            {'id': 18000, 'ip': '10.40.75.32', 'name': 'VENTILACION-S3-S4-F2'},
            {'id': 15000, 'ip': '10.40.102.26', 'name': 'CBC-PB-ILUMINACION-UPS'},
            {'id': 2000, 'ip': '10.40.100.25', 'name': 'CBA-PB-SUBESTACION'},
            {'id': 25000, 'ip': '10.40.20.26', 'name': 'T1-N1-ILUMINACION-UPS'},
            {'id': 9000, 'ip': '10.40.101.26', 'name': 'CBB-PB-SUBESTACION'},
            {'id': 26000, 'ip': '10.40.20.27', 'name': 'T1-N1-SUBESTACION'},
            {'id': 23000, 'ip': '10.40.20.21', 'name': 'T1-N23-HVAC1'},
            {'id': 24000, 'ip': '10.40.20.22', 'name': 'T1-N23-HVAC2'},
            {'id': 17000, 'ip': '10.40.75.31', 'name': 'VENTILACION-S1-S2-F2'},
            {'id': 11000, 'ip': '10.40.50.47', 'name': 'T2-N1-ILUMINACION-UPS'},
            {'id': 1000, 'ip': '10.40.100.21', 'name': 'MACH-ProCom-MAIN'},
        ]

        count = 0
        for dev in devices_data:
            obj, created = BACnetDevice.objects.update_or_create(
                device_id=dev['id'],
                defaults={
                    'gateway': gateway,
                    'name': dev['name'],
                    'address': dev['ip'],
                    'vendor': 'Reliable Controls Corp.',
                    'is_online': True # Marcamos como online inicialmente
                }
            )
            count += 1
            self.stdout.write(f'  [OK] Provisionado: {dev["name"]} ({dev["ip"]})')

        self.stdout.write(self.style.SUCCESS(f'\n[FIN] {count} dispositivos provisionados exitosamente.'))
