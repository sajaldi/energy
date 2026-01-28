import os
import django
import sys

# Setup paths
curr_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(curr_dir)

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energy.settings')
django.setup()

from mantenimiento.views.api import api_get_assets_wizard
from mantenimiento.models import Rutina, Categoria
from activos.models import Activo, Categoria as CategoriaActivo, Ubicacion
import json

def test_filtering():
    factory = RequestFactory()
    
    # 1. Test filtering by routine category
    # Find a routine with a category that has assets
    rutina = Rutina.objects.filter(categoria__categoria_activo__isnull=False).first()
    if not rutina:
        print("No routine found with an asset category linked.")
        return

    print(f"Testing with Routine: {rutina.nombre}, Category: {rutina.categoria.nombre}")
    
    # Create request simulating Step 4 logic
    request = factory.get('/mantenimiento/api/get-assets-wizard/', {
        'rutina_id': rutina.id
    })
    
    response = api_get_assets_wizard(request)
    data = json.loads(response.content)
    
    print(f"Found {len(data['activos'])} assets.")
    for a in data['activos'][:5]:
        print(f"- {a['nombre']} ({a['categoria']})")
        
    # Verify that assets belong to the correct category
    asset_cat_id = rutina.categoria.categoria_activo_id
    allowed_cats = set(CategoriaActivo.objects.get(id=asset_cat_id).get_descendants(include_self=True).values_list('nombre', flat=True))
    
    for a in data['activos']:
        if a['categoria'] not in allowed_cats:
            print(f"FAILED: Asset {a['nombre']} has category {a['categoria']}, not in {allowed_cats}")
            return
            
    print("SUCCESS: All assets belong to the routine category subtree.")

    # 2. Test filtering by area AND routine category
    area = Ubicacion.objects.first()
    print(f"\nTesting with Routine: {rutina.nombre} AND Area: {area.nombre}")
    
    request = factory.get('/mantenimiento/api/get-assets-wizard/')
    # Simulate areas[] parameter manually since RequestFactory.get handles it differently
    q = QueryDict(mutable=True)
    q.setlist('areas[]', [str(area.id)])
    q['rutina_id'] = str(rutina.id)
    request.GET = q
    
    response = api_get_assets_wizard(request)
    data = json.loads(response.content)
    print(f"Found {len(data['activos'])} assets in area {area.nombre} with routine category.")
    
    for a in data['activos'][:5]:
        print(f"- {a['nombre']} | {a['ubicacion']} | {a['categoria']}")

if __name__ == "__main__":
    test_filtering()
