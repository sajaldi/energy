import os
import sys
import django

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from presupuestos.models import PresupuestoAnual, Moneda

try:
    print("--- Monedas en el sistema ---")
    for m in Moneda.objects.all():
        print(f"ID: {m.id} | Codigo: {m.codigo} | Nombre: {m.nombre} | Simbolo: {m.simbolo}")
        
    print("\n--- Presupuestos Anuales y sus Monedas ---")
    for p in PresupuestoAnual.objects.all():
        print(f"Presupuesto: {p.nombre} | Moneda Str: {p.moneda} | Moneda Codigo: {p.moneda.codigo} | Moneda ID: {p.moneda_id}")
        
except Exception as e:
    print(f"Error: {e}")
