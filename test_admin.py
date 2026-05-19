import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User

c = Client()
user = User.objects.filter(is_superuser=True).first()
if user:
    c.force_login(user)
    response = c.get('/admin/seguridad/analisisriesgo/')
    print("Status:", response.status_code)
    with open('admin_output.html', 'wb') as f:
        f.write(response.content)
    print("Saved to admin_output.html")
else:
    print("No superuser found")
