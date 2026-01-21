import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from activos.models import Activo

try:
    obj = Activo.objects.get(id=95503)
    print(f"Activo: {obj}")
    count = obj.componentes.count()
    print(f"Direct components count: {count}")
    
    # Check if recursion is huge
    def count_recursive(activo):
        c = activo.componentes.count()
        total = c
        for child in activo.componentes.all():
            total += count_recursive(child)
        return total
        
    # print(f"Recursive descendants: {count_recursive(obj)}") 
    # Don't run recursive if direct is huge
    
except Activo.DoesNotExist:
    print("Activo 95503 not found")
