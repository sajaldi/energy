import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energy.settings')
django.setup()

from activos.models import Activo

blank_codigos = Activo.objects.filter(codigo_interno='')
print(f"Encontrados {blank_codigos.count()} activos con codigo_interno vacío.")
for a in blank_codigos[:10]:
    print(f"ID: {a.id}, Nombre: {a.nombre}")

null_codigos = Activo.objects.filter(codigo_interno__isnull=True)
print(f"Encontrados {null_codigos.count()} activos con codigo_interno NULL.")
