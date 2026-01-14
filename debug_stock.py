import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from inventarios.models import SolicitudMaterial, StockRecord
from activos.models import Ubicacion

try:
    sol = SolicitudMaterial.objects.get(id=1)
    print(f"ORDEN ID: {sol.id}")
    print(f"ORIGEN: {sol.ubicacion_origen.nombre} (ID: {sol.ubicacion_origen.id})")
    
    # Obtener descendientes
    desc_ids = sol.ubicacion_origen.get_descendants().values_list('id', flat=True)
    print(f"DESCENDIENTES IDs: {list(desc_ids)}")
    
    items = sol.items.all()
    
    for i in items:
        print(f"\nITEM: {i.material.nombre}")
        
        # Búsqueda recursiva
        srs = StockRecord.objects.filter(material=i.material, ubicacion__in=desc_ids, cantidad__gt=0)
        print(f"STOCK RECORDS ENCONTRADOS (RECURSIVOS): {srs.count()}")
        for s in srs:
            print(f"  - ALMACEN: {s.ubicacion.nombre}, UBICACION ESPECIFICA: {s.ubicacion_especifica or 'NADA'}, CANTIDAD: {s.cantidad}")
            
except Exception as e:
    import traceback
    traceback.print_exc()
