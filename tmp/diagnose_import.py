import os
import django
import sys

# Setup Django
sys.path.append(r'd:\Apps\energia\energy')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energy.settings')
django.setup()

from django.apps import apps
from django.db import models

print("Searching for Categoria import errors...")

for app_config in apps.get_app_configs():
    app_name = app_config.name
    try:
        # Try to import models for each app
        __import__(f"{app_name}.models")
    except ImportError as e:
        if 'Categoria' in str(e) and 'mantenimiento' in str(e):
            print(f"Error in {app_name}.models: {e}")
    except Exception:
        pass

    try:
        # Try to import admin for each app
        __import__(f"{app_name}.admin")
    except ImportError as e:
        if 'Categoria' in str(e) and 'mantenimiento' in str(e):
            print(f"Error in {app_name}.admin: {e}")
    except Exception:
        pass
