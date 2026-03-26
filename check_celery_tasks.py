import os
import sys
from celery import Celery

# Setup environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')

app = Celery('energia')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

print("Registered Tasks:")
for task in sorted(app.tasks.keys()):
    print(f"- {task}")
