import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "energy.settings")
import django
django.setup()
from django.contrib.auth.models import User
from mantenimiento.models import Falla, TecnicoPuesto

user = User.objects.get(username='saul.alvarado')
puesto_tecnico = user.perfil_tecnico
roots = Falla.objects.filter(puestos_trabajo=puesto_tecnico.puesto)
fallas_ids = []

def get_ids(node):
    fallas_ids.append(node.id)
    for h in node.hijos.all(): 
        get_ids(h)

for r in roots:
    get_ids(r)

universales = Falla.objects.filter(puestos_trabajo__isnull=True, padre__isnull=True)
for u in universales:
    get_ids(u)

fallas = Falla.objects.filter(id__in=fallas_ids)
import json
fallas_data = []
for f in fallas:
    fallas_data.append({
        'id': f.id,
        'nombre': f.get_ruta_completa(),
        'tipo_aviso': f.tipo_aviso or ''
    })
print(json.dumps(fallas_data, ensure_ascii=False, indent=2))
