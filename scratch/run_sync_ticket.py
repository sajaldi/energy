import os
import django
from dotenv import load_dotenv

# Load env variables from .env
load_dotenv()

# Setup environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from callcenter.tasks import sync_single_ticket_task

print("--- INICIANDO PRUEBA DE SINCRONIZACION DE TICKET INDIVIDUAL ---")
ticket_id = 45251 # SS26-146869
print(f"Probando ticket ID: {ticket_id}")

try:
    # Llamamos a la función directamente para ver los prints en tiempo real
    resultado = sync_single_ticket_task(ticket_id)
    print("\n--- RESULTADO ---")
    print(resultado)
except Exception as e:
    print(f"\n--- ERROR EN EJECUCIÓN ---")
    import traceback
    traceback.print_exc()
