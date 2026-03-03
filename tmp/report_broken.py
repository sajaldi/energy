
from mantenimiento.models import Categoria, Rutina, OrdenTrabajo
from activos.models import Ubicacion, Activo
import collections

broken_values = collections.defaultdict(set)

def collect_unique_broken_values(model, fields, name):
    for field in fields:
        # Check for both literal ?? and the unicode replacement character
        q_results = model.objects.filter(**{f"{field}__icontains": "??"}) | model.objects.filter(**{f"{field}__icontains": "\ufffd"})
        for obj in q_results:
            val = getattr(obj, field)
            if val:
                broken_values[name].add(val)

collect_unique_broken_values(Ubicacion, ['nombre'], 'Ubicacion')
collect_unique_broken_values(Activo, ['nombre', 'descripcion'], 'Activo')
collect_unique_broken_values(Rutina, ['nombre', 'descripcion'], 'Rutina')
collect_unique_broken_values(OrdenTrabajo, ['notas', 'descripcion_corta'], 'OrdenTrabajo')
collect_unique_broken_values(Categoria, ['nombre'], 'Categoria')

with open('tmp/broken_report.txt', 'w', encoding='utf-8') as f:
    for model_name in sorted(broken_values.keys()):
        values = broken_values[model_name]
        if values:
            f.write(f"\n{model_name}:\n")
            for v in sorted(values):
                f.write(f" - {v}\n")
print("Reporte generado en tmp/broken_report.txt")
