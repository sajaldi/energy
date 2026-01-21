import os
import django
import time
from collections import defaultdict

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from activos.models import Activo, Categoria
from django.db.models import Count
from django.shortcuts import get_object_or_404

def debug_query():
    parent_id = 95503 # ID from previous check
    print(f"DEBUG: Checking duplicates for parent {parent_id}")
    
    try:
        activo_padre = Activo.objects.get(id=parent_id)
        
        # Exact query from views.py
        hijos = activo_padre.componentes.annotate(
            num_hijos=Count('componentes')
        ).select_related('modelo__categoria', 'ubicacion').order_by('nombre')
        
        hijos_list = list(hijos)
        print(f"Total results: {len(hijos_list)}")
        
        seen = set()
        dupes = []
        for h in hijos_list:
            if h.id in seen:
                dupes.append(h)
            seen.add(h.id)
            print(f" - [{h.id}] {h.nombre} (Hijos: {h.num_hijos})")
            
        if dupes:
            print(f"!!! FOUND {len(dupes)} DUPLICATES !!!")
        else:
            print("No duplicates found with current query.")
            
    except Activo.DoesNotExist:
        print("Activo not found")

if __name__ == '__main__':
    debug_query()
