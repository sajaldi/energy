from django.core.management.base import BaseCommand
from presupuestos.models import Requisicion, RequisicionHistorial


class Command(BaseCommand):
    help = 'Crea registros de historial para requisiciones existentes que no tienen historial'

    def handle(self, *args, **options):
        total = 0
        for req in Requisicion.objects.all():
            if not req.historial.exists():
                RequisicionHistorial.objects.create(
                    requisicion=req,
                    estado_anterior=None,
                    estado_nuevo=req.estado_requisicion,
                    descripcion="Registro inicial (backfill)",
                )
                if req.fecha_aprobacion and req.estado_requisicion in ('AUTORIZADO', 'VISTO_PROCURA', 'PROCURA_PROCESANDO', 'EN_ORDEN_COMPRA'):
                    RequisicionHistorial.objects.create(
                        requisicion=req,
                        estado_anterior=None,
                        estado_nuevo='AUTORIZADO',
                        creado_en=req.fecha_aprobacion,
                        descripcion="Aprobado (backfill)",
                    )
                total += 1
                if total % 100 == 0:
                    self.stdout.write(f"  Procesadas {total} requisiciones...")
        self.stdout.write(self.style.SUCCESS(f"Historial creado para {total} requisiciones."))
