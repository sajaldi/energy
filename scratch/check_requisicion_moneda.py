import os
import sys
import django

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from presupuestos.models import Requisicion

try:
    print("--- Moneda en Requisiciones ---")
    reqs = Requisicion.objects.filter(partida__isnull=False)[:5]
    if not reqs.exists():
        print("No hay requisiciones con partida asignada.")
        # Print a normal one
        reqs = Requisicion.objects.all()[:5]
        
    for r in reqs:
        print(f"Requisicion: {r.cr8ca_requisicion} | Partida: {r.partida} | Moneda property: {r.moneda}")
except Exception as e:
    print(f"Error: {e}")
