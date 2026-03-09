import os
import django
from django.conf import settings
from django.core.files.storage import default_storage

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

path = 'hotspots/test.jpg'
url_manual = os.path.join(settings.MEDIA_URL, path).replace("\\", "/")
url_storage = default_storage.url(path)

print(f"MEDIA_URL: {settings.MEDIA_URL}")
print(f"Manual URL: {url_manual}")
print(f"Storage URL: {url_storage}")
