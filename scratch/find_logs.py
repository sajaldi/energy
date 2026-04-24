import os
import sys
import django

# Add project root to path
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from core.utils_ssh import get_ssh_client

try:
    ssh = get_ssh_client()
    # List possible log locations in Coolify v4
    commands = [
        'ls -d /data/coolify/ssh/logs/* 2>/dev/null | head -n 5',
        'ls -d /data/coolify/storage/app/deployments/* 2>/dev/null | head -n 5',
        'docker ps -a --filter "name=build" --format "{{.Names}}"'
    ]
    for cmd in commands:
        print(f"--- Running: {cmd} ---")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        print(stdout.read().decode())
    ssh.close()
except Exception as e:
    print(f"Error: {e}")
