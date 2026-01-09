import os
import django
import sys

# Setup Django environment
sys.path.append('D:/Apps/energia/energy')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from django.urls import reverse, resolve
from django.conf import settings

print("--- Checking URL Reverse ---")
try:
    url = reverse('auditorias:lista_auditorias')
    print(f"SUCCESS: 'auditorias:lista_auditorias' -> {url}")
except Exception as e:
    print(f"FAILURE: 'auditorias:lista_auditorias': {e}")

try:
    url = reverse('lista_auditorias')
    print(f"SUCCESS: 'lista_auditorias' -> {url}")
except Exception as e:
    print(f"INFO: 'lista_auditorias' (no namespace) -> {e}")

print("\n--- Checking Resolver ---")
try:
    res = resolve('/auditorias/')
    print(f"Resolution success: {res.view_name}, {res.func}")
except Exception as e:
    print(f"Resolution failed for /auditorias/: {e}")

try:
    norm = resolve('/auditorias')
    print(f"Resolution success for /auditorias: {norm.view_name}")
except:
    pass

print("\n--- Checking Installed Apps ---")
if 'auditorias' in settings.INSTALLED_APPS:
    print("SUCCESS: 'auditorias' is in INSTALLED_APPS")
else:
    print("FAILURE: 'auditorias' is NOT in INSTALLED_APPS")

print("\n--- Checking ActivoResource ---")
try:
    from activos.admin import ActivoResource
    from activos.models import Activo, Ubicacion
    
    print("Initializing ActivoResource...")
    resource = ActivoResource()
    # Dummy dataset simulation if needed, but just initialization checks imports
    print("ActivoResource initialized.")
    
    # Check cache logic
    print("Checking cache logic in before_import...")
    # Mock dataset
    from tablib import Dataset
    dataset = Dataset()
    dataset.headers = ['codigo_interno', 'nombre', 'ubicacion_nombre', 'modelo_nombre']
    
    # Run before_import
    class MockUser:
        id = 1
    
    resource.before_import(dataset, user=MockUser())
    print("before_import executed successfully.")
    
except Exception as e:
    print(f"FAILURE: ActivoResource check failed: {e}")
    import traceback
    traceback.print_exc()
