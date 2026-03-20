import os
import django
import json
import base64

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from callcenter.models import SolicitudTicket, EvidenciaTicket

ticket = SolicitudTicket.objects.last()
if not ticket:
    print("No tickets found.")
else:
    print(f"Checking Ticket: {ticket.folio}")
    evidencias = ticket.evidencias.all()
    print(f"Found {len(evidencias)} evidencia(s).")
    for ev in evidencias:
        exists = os.path.exists(ev.archivo.path) if ev.archivo else False
        size = os.path.getsize(ev.archivo.path) if exists else 0
        print(f"ID: {ev.id}, File: {ev.archivo.name}, Exists: {exists}, Size: {size}, Desc: {ev.descripcion}")
