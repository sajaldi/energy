
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energy.settings')
django.setup()

from activos.models import Modelo

m = Modelo.objects.filter(nombre__icontains='AM036').first()
if m:
    print(f"ID: {m.id}")
    print(f"Nombre: {m.nombre}")
    if m.categoria:
        print(f"Categoria ID: {m.categoria.id}")
        print(f"Categoria Nombre: {m.categoria.nombre}")
    else:
        print("Categoria: None")
else:
    print("Modelo no encontrado")
