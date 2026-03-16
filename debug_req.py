import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from presupuestos.models import Requisicion

def test():
    req = Requisicion.objects.last()
    if not req:
        print("No hay requisiciones.")
        return
    
    print(f"Campos disponibles en Requisicion: {dir(req)}")
    try:
        print(f"Asunto: {req.cr8ca_asunto}")
    except Exception as e:
        print(f"Error accediendo a cr8ca_asunto: {e}")

if __name__ == "__main__":
    test()
