from django.core.management.base import BaseCommand
from callcenter.models import SolicitudTicket, Enlace, Institucion


class Command(BaseCommand):
    help = 'Crea Enlaces para todos los tickets que aún no tienen enlace_solicitante'

    def handle(self, *args, **options):
        total = SolicitudTicket.objects.filter(enlace_solicitante__isnull=True).count()
        self.stdout.write(f"Tickets sin enlace: {total}")

        inst = Institucion.objects.first()
        if not inst:
            inst = Institucion.objects.create(nombre='Sin Institución')

        BATCH = 500
        procesados = 0
        creados = 0
        ids_to_update = []
        cache = {}  # nombre.lower() -> enlace_id

        qs = SolicitudTicket.objects.filter(enlace_solicitante__isnull=True).only('id', 'solicitante').iterator()

        for ticket in qs:
            name = (ticket.solicitante or '').strip()
            if not name:
                continue

            key = name.lower()
            eid = cache.get(key)
            if eid is None:
                parts = name.split(maxsplit=2)
                nom = parts[0]
                ap1 = parts[1] if len(parts) > 1 else ''
                ap2 = parts[2] if len(parts) > 2 else ''

                enlace, _ = Enlace.objects.get_or_create(
                    nombre=nom,
                    primer_apellido=ap1,
                    segundo_apellido=ap2,
                    institucion=inst,
                )
                if _:
                    creados += 1
                eid = enlace.id
                cache[key] = eid

            ids_to_update.append((ticket.id, eid))
            procesados += 1

            if len(ids_to_update) >= BATCH:
                self._bulk_update(ids_to_update)
                self.stdout.write(f"  Procesados {procesados}/{total} (creados {creados})")
                ids_to_update = []

        if ids_to_update:
            self._bulk_update(ids_to_update)

        self.stdout.write(self.style.SUCCESS(f"Procesados {procesados} tickets. Enlaces creados: {creados}"))

    def _bulk_update(self, pairs):
        objs = [SolicitudTicket(id=pk, enlace_solicitante_id=eid) for pk, eid in pairs]
        SolicitudTicket.objects.bulk_update(objs, ['enlace_solicitante'])
