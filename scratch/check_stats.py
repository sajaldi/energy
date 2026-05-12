from callcenter.models import SolicitudTicket
from activos.models.ubicacion import Ubicacion
from callcenter.models import FallaTicket
from django.db.models import Count

print(f"Total Tickets: {SolicitudTicket.objects.count()}")
print(f"Unique Locations in Tickets: {SolicitudTicket.objects.values('ubicacion_id').distinct().count()}")
print(f"Unique Failures in Tickets: {SolicitudTicket.objects.values('falla_reportada_id').distinct().count()}")
print(f"Total Ubicaciones: {Ubicacion.objects.count()}")
print(f"Total Fallas: {FallaTicket.objects.count()}")
