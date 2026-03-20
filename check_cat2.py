import os
import sys
import django

sys.path.append(r'd:\Apps\energia\energy')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from activos.models import Categoria

cats = Categoria.objects.filter(nombre__icontains='TRANSFERENCIA')
print(f"Buscando 'TRANSFERENCIA' en categorias de activos:")
if cats.exists():
    for c in cats:
        padre_nombre = c.padre.nombre if c.padre else 'ROOT (None)'
        print(f"- {c.nombre} | Padre: {padre_nombre}")
else:
    print("No se encontró ninguna categoría con ese nombre.")
