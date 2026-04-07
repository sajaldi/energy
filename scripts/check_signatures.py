import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energy.settings')
django.setup()

from callcenter.models import TiempoAcordado

acuerdo = TiempoAcordado.objects.all().order_by('-id').first()
if acuerdo:
    print(f"Acuerdo ID: {acuerdo.id}")
    fr = acuerdo.firma_responsable
    fe = acuerdo.firma_enlace
    print(f"Firma Responsable (len): {len(fr) if fr else 0}")
    print(f"Firma Responsable (start): {fr[:50] if fr else 'None'}")
    print(f"Firma Enlace (len): {len(fe) if fe else 0}")
    print(f"Firma Enlace (start): {fe[:50] if fe else 'None'}")
else:
    print("No hay acuerdos.")
