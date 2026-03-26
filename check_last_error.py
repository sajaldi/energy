import os
import django
import sys

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from activos.models import RegistroImportacion

# Obtener la última importación de Pasos de Rutina
last_imp = RegistroImportacion.objects.filter(tipo='Pasos de Rutina').order_by('-id').first()

if last_imp:
    print(f"ID: {last_imp.id}")
    print(f"Nombre: {last_imp.nombre}")
    print(f"Estado: {last_imp.estado}")
    print(f"Filas: {last_imp.total_filas} (N:{last_imp.filas_nuevas}, A:{last_imp.filas_actualizadas}, E:{last_imp.filas_error})")
    print(f"Error: {last_imp.detalles_error}")
else:
    print("No se encontraron registros de importación para 'Pasos de Rutina'.")
