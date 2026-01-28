import os
import django
import sys
import json

# Setup Django using the current working directory
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energy.settings')
django.setup()

from mantenimiento.views.api import api_get_assets_wizard
from mantenimiento.models import Rutina
from activos.models import Categoria as CategoriaActivo, Ubicacion
from django.test import RequestFactory
from django.http import QueryDict

def test_filtering():
    factory = RequestFactory()
    
    # 1. Test filtering by routine category
    rutina = Rutina.objects.filter(categoria__categoria_activo__isnull=False).first()
    if not rutina:
        print("No routine found with an asset category linked.")
        return

    print(f"Testing with Routine: {rutina.nombre}, Routine Category: {rutina.categoria.nombre}")
    
    request = factory.get('/mantenimiento/api/get-assets-wizard/', {
        'rutina_id': rutina.id
    })
    
    response = api_get_assets_wizard(request)
    data = json.loads(response.content)
    
    print(f"Found {len(data['activos'])} assets.")
    
    # Verify that assets belong to the correct category
    asset_cat_id = rutina.categoria.categoria_activo_id
    allowed_cats_ids = set(CategoriaActivo.objects.get(id=asset_cat_id).get_descendants(include_self=True).values_list('id', flat=True))
    allowed_cats_names = set(CategoriaActivo.objects.filter(id__in=allowed_cats_ids).values_list('nombre', flat=True))
    
    print(f"Allowed Asset Categories: {allowed_cats_names}")

    success = True
    for a in data['activos']:
        if a['categoria'] not in allowed_cats_names:
            print(f"FAILED: Asset {a['nombre']} has category {a['categoria']}, not in allowed list.")
            success = False
            break
            
    if success and data['activos']:
        print("SUCCESS: All assets belong to the routine category subtree.")
    elif not data['activos']:
        print("WARNING: No assets found for this category, but query executed successfully.")

    # 2. Test filtering by area AND routine category
    area = Ubicacion.objects.first()
    if area:
        print(f"\nTesting with Routine: {rutina.nombre} AND Area: {area.nombre}")
        
        request = factory.get('/mantenimiento/api/get-assets-wizard/')
        q = QueryDict(mutable=True)
        q.setlist('areas[]', [str(area.id)])
        q['rutina_id'] = str(rutina.id)
        request.GET = q
        
        response = api_get_assets_wizard(request)
        data = json.loads(response.content)
        print(f"Found {len(data['activos'])} assets in area {area.nombre} with routine category.")
        
        if data['status'] == 'success':
            print("SUCCESS: Query with area and routine_id worked.")

if __name__ == "__main__":
    test_filtering()
