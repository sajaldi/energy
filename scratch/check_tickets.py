import os
import django

# Setup environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from callcenter.models import SolicitudTicket

tickets = SolicitudTicket.objects.exclude(fecha_cierre=None).order_by('-fecha_cierre')[:10]
print(f"Encontrados {tickets.count()} tickets con fecha de cierre:")
for t in tickets:
    print(f"ID: {t.id} | Folio: {t.folio} | Fecha Solicitud: {t.fecha_solicitud} | Fecha Cierre: {t.fecha_cierre} | Diagnostico: {t.diagnostico[:50] if t.diagnostico else 'Ninguno'}")
