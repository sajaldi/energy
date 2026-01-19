import os
import django
import sys

# Add project root to path
sys.path.append(os.getcwd())

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "energia.settings")
django.setup()

from django.contrib import admin
from activos.models import Activo
from django.urls import reverse

print("--- DEBUGGING ACTIVO ADMIN ---")

if Activo in admin.site._registry:
    model_admin = admin.site._registry[Activo]
    print(f"REGISTERED CLASS: {model_admin.__class__.__name__}")
    print(f"MODULE: {model_admin.__class__.__module__}")
    
    print("\n--- URLs ---")
    urls = model_admin.get_urls()
    found = False
    for u in urls:
        name = getattr(u, 'name', 'No Name')
        print(f"Pattern: {u.pattern} | Name: {name}")
        if name == 'activos_activo_import_background_redis':
            found = True
            
    print(f"\nTARGET URL FOUND IN LIST: {found}")
    
    print("\n--- REVERSE CHECK ---")
    try:
        url = reverse('admin:activos_activo_import_background_redis')
        print(f"SUCCESS! Resolved to: {url}")
    except Exception as e:
        print(f"FAILED to reverse: {e}")
        
else:
    print("CRITICAL: Activo model is NOT registered in admin.site")
