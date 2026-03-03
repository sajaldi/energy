
from mantenimiento.models import Categoria, Rutina, OrdenTrabajo
from activos.models import Ubicacion, Activo

def search_broken_chars(model, fields):
    print(f"\n--- Buscando en {model.__name__} ---")
    any_found = False
    for field in fields:
        # Buscamos '??' literal y el carácter de reemplazo de unicode
        q_results = model.objects.filter(**{f"{field}__icontains": "??"}) | model.objects.filter(**{f"{field}__icontains": "\ufffd"})
        if q_results.exists():
            any_found = True
            for obj in q_results:
                print(f"ID: {obj.pk} | Campo: {field} | Valor: {getattr(obj, field)}")
    if not any_found:
        print("No se encontraron registros con caracteres rotos.")

search_broken_chars(Ubicacion, ['nombre'])
search_broken_chars(Activo, ['nombre', 'descripcion'])
search_broken_chars(Rutina, ['nombre', 'descripcion'])
search_broken_chars(OrdenTrabajo, ['notas', 'descripcion_corta'])
search_broken_chars(Categoria, ['nombre'])
