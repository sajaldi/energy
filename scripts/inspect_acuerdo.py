import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energy.settings')
django.setup()

from callcenter.models import TiempoAcordado

# Buscamos el acuerdo de la captura por el folio del ticket
folio_target = "SS26-142020"
acuerdos = TiempoAcordado.objects.filter(ticket__folio=folio_target)

if acuerdos.exists():
    for ac in acuerdos:
        print(f"--- Acuerdo ID: {ac.id} ---")
        print(f"Ticket Folio: {ac.ticket.folio}")
        fr = ac.firma_responsable
        fe = ac.firma_enlace
        print(f"Firma Responsable (len): {len(fr) if fr else 0}")
        print(f"Firma Responsable (preview): {fr[:100] if fr else 'None'}")
        print(f"Firma Enlace (len): {len(fe) if fe else 0}")
        print(f"Firma Enlace (preview): {fe[:100] if fe else 'None'}")
else:
    print(f"No se encontró acuerdo para el ticket {folio_target}")
