import os
import json
import django
from django.test import Client

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energy.settings.local')
django.setup()

client = Client()
from django.contrib.auth.models import User
admin = User.objects.filter(is_superuser=True).first()

client.force_login(admin)
payload = {
    "estado": [],
    "ubicacion": [],
    "familia": [],
    "marca": [],
    "modelo": [],
    "busqueda": ""
}
response = client.post('/activos/celery-import/filter/export/', json.dumps(payload), content_type='application/json')

print(f"Status Code: {response.status_code}")
if response.status_code == 500:
    print(response.content.decode()[:1000])
elif response.status_code == 200:
    print("Export successful, size:", len(response.content))
else:
    print(response.content.decode()[:1000])
