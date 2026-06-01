import os
import sys
import django

# Setup environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from celery import Celery

app = Celery('energia')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks(['mantenimiento', 'presupuestos', 'servicios', 'activos', 'callcenter', 'core', 'documentos'])

print("Registered Tasks:")
for task in sorted(app.tasks.keys()):
    print(f"- {task}")

