import os
import django
from datetime import datetime, timezone, timedelta

# Setup environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from callcenter.models import SolicitudTicket

ticket = SolicitudTicket.objects.get(folio="SS26-146869")
print(f"Ticket Folio: {ticket.folio}")
print(f"Fecha Solicitud actual: {ticket.fecha_solicitud}")
print(f"Fecha Cierre actual: {ticket.fecha_cierre}")

# Establecer fecha_cierre a las 12:45:00 (Honduras time), que es 18:45:00 UTC
honduras_tz = timezone(timedelta(hours=-6))
nueva_fecha_cierre = datetime(2026, 5, 23, 18, 45, 0, tzinfo=timezone.utc)
ticket.fecha_cierre = nueva_fecha_cierre
ticket.save()

print("\n--- ACTUALIZACIÓN ---")
ticket.refresh_from_db()
print(f"Nueva Fecha Cierre: {ticket.fecha_cierre}")
