import os
import django
import sys
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from callcenter.tasks import sync_tickets_task

print("--- INICIANDO PRUEBA DE SINCRONIZACION ---")
# Probar con un rango de fechas específico solicitado por el usuario
fecha_ini = "29/04/2026"
fecha_fin = "01/05/2026"

print(f"Probando rango: {fecha_ini} al {fecha_fin}")

try:
    # Llamamos a la función directamente (no .delay() para ver logs aquí)
    # Esto descargará el archivo y tratará de importarlo
    resultado = sync_tickets_task(fecha_inicio=fecha_ini, fecha_fin=fecha_fin)
    print("\n--- RESULTADO ---")
    print(resultado)
except Exception as e:
    print(f"\n--- ERROR ---")
    print(e)
