import os
import sys
import django
from datetime import datetime
from dotenv import load_dotenv

# Configurar Django
sys.path.append('d:\\Apps\\energia\\energy')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from callcenter.scraper import sync_individual_ticket
from callcenter.models import SolicitudTicket

load_dotenv()

def test_sync():
    folio = 'SS26-138719'
    ticket = SolicitudTicket.objects.filter(folio=folio).first()
    if not ticket:
        print("Ticket no encontrado en DB")
        return

    username = os.environ.get('CALLCENTER_USER')
    password = os.environ.get('CALLCENTER_PASS')
    company = "Centro Cívico Gubernamental de Honduras"

    print(f"Iniciando prueba para folio: {folio}")
    result = sync_individual_ticket(
        username=username,
        password=password,
        company_name=company,
        ticket_folio=folio,
        fecha_solicitud=ticket.fecha_solicitud
    )
    print(result)

if __name__ == "__main__":
    test_sync()
