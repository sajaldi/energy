import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from presupuestos.models import Requisicion
from presupuestos.utils_documentos import generate_requisicion_pdf

def test():
    req = Requisicion.objects.last()
    if not req:
        return

    doc = generate_requisicion_pdf(req)
    if doc:
        print(f"URL: {doc.archivo.url}")

if __name__ == "__main__":
    test()
