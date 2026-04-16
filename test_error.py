import os
import django
from django.test import Client

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energy.settings.local')
django.setup()

client = Client()
# We need to bypass login via a quick trick or test client force login
from django.contrib.auth.models import User
admin = User.objects.filter(is_superuser=True).first()

client.force_login(admin)
response = client.get('/activos/celery-import/filter-options/')

print(f"Status Code: {response.status_code}")
if response.status_code == 500:
    print(response.content.decode())
else:
    print("Success")
