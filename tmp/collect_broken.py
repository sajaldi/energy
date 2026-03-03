
from mantenimiento.models import Categoria, Rutina, OrdenTrabajo
from activos.models import Ubicacion, Activo

broken_values = {
    'Ubicacion': set(),
    'Activo': set(),
    'Rutina': set(),
    'OrdenTrabajo': set(),
    'Categoria': set()
}

def collect_unique_broken_values(model, fields, name):
    for field in fields:
        q_results = model.objects.filter(**{f"{field}__icontains": "??"}) | model.objects.filter(**{f"{field}__icontains": "\ufffd"})
        for obj in q_results:
            broken_values[name].add(getattr(obj, field))

collect_unique_broken_values(Ubicacion, ['nombre'], 'Ubicacion')
collect_unique_broken_values(Activo, ['nombre', 'descripcion'], 'Activo')
collect_unique_broken_values(Rutina, ['nombre', 'descripcion'], 'Rutina')
collect_unique_broken_values(OrdenTrabajo, ['notas', 'descripcion_corta'], 'OrdenTrabajo')
collect_unique_broken_values(Categoria, ['nombre'], 'Categoria')

for model_name, values in broken_values.items():
    if values:
        print(f"\n{model_name}:")
        for v in sorted(values):
            print(f" - {v}")
