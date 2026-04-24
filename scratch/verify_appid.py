import os
import sys
import django

# Add project root to path
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from core.utils_ssh import get_coolify_containers

containers = get_coolify_containers()
for c in containers:
    print(f"Container: {c['name']}, AppID: {c.get('application_id')}")
