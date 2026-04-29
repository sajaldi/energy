from django.core.management.base import BaseCommand
from iot.models import BACnetDevice, BACnetPoint

class Command(BaseCommand):
    help = 'Registra los puntos de telemetria descubiertos en el dispositivo principal'

    def handle(self, *args, **options):
        try:
            device = BACnetDevice.objects.get(device_id=11000)
            
            points_to_create = [
                {'name': 'Voltaje A-B OUT', 'obj_type': 'analog-value', 'obj_inst': 1, 'unit': 'V'},
                {'name': 'Voltaje B-C OUT', 'obj_type': 'analog-value', 'obj_inst': 2, 'unit': 'V'},
                {'name': 'Voltaje C-A OUT', 'obj_type': 'analog-value', 'obj_inst': 3, 'unit': 'V'},
                {'name': 'Corriente Ia IN', 'obj_type': 'analog-value', 'obj_inst': 10, 'unit': 'A'},
                {'name': 'Corriente Ib IN', 'obj_type': 'analog-value', 'obj_inst': 11, 'unit': 'A'},
                {'name': 'Corriente Ic IN', 'obj_type': 'analog-value', 'obj_inst': 12, 'unit': 'A'},
                {'name': 'Voltaje Bateria', 'obj_type': 'analog-value', 'obj_inst': 16, 'unit': 'V'},
                {'name': 'Tiempo Restante', 'obj_type': 'analog-value', 'obj_inst': 14, 'unit': 'min'},
            ]

            count = 0
            for p in points_to_create:
                obj, created = BACnetPoint.objects.update_or_create(
                    device=device,
                    object_type=p['obj_type'],
                    instance=p['obj_inst'],
                    defaults={
                        'name': p['name'],
                        'unit': p['unit']
                    }
                )
                count += 1
                self.stdout.write(f'  [OK] Punto registrado: {p["name"]} ({p["obj_type"]} {p["obj_inst"]})')

            self.stdout.write(self.style.SUCCESS(f'\n[FIN] {count} puntos de telemetria registrados.'))
        except BACnetDevice.DoesNotExist:
            self.stdout.write(self.style.ERROR('No se encontro el dispositivo 11000. Ejecuta primero provision_iot.'))
