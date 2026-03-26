import os
import django
import sys

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from django.core.cache import cache

# Reemplazar con el ID de usuario real si se conoce, o probar con los comunes
user_id = 1 # Saúl suele ser el 1
cache_key = f"import_pasos_progress_{user_id}"
progress = cache.get(cache_key)

print(f"Cache Key: {cache_key}")
print(f"Content: {progress}")

# Probar sin ID por si acaso
cache_key_sys = "import_pasos_progress_system"
progress_sys = cache.get(cache_key_sys)
print(f"Cache Key: {cache_key_sys}")
print(f"Content: {progress_sys}")
