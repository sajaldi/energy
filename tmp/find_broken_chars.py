
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from mantenimiento.models import Categoria, Rutina, OrdenTrabajo
from activos.models import Ubicacion, Activo

def search_broken_chars(model, fields):
    print(f"--- Buscando en {model.__name__} ---")
    query = model.objects.none()
    for field in fields:
        # Buscamos '??' literal y el carácter de reemplazo de unicode
        q_results = model.objects.filter(**{f"{field}__icontains": "??"}) | model.objects.filter(**{f"{field}__icontains": "\ufffd"})
        if q_results.exists():
            for obj in q_results:
                print(f"ID: {obj.pk} | Campo: {field} | Valor: {getattr(obj, field)}")

if __name__ == "__main__":
    search_broken_chars(Ubicacion, ['nombre'])
    search_broken_chars(Activo, ['nombre', 'descripcion'])
    search_broken_chars(Rutina, ['nombre', 'descripcion'])
    search_broken_chars(OrdenTrabajo, ['notas', 'descripcion_corta'])
    search_broken_chars(Categoria, ['nombre'])
