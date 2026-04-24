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
    # Find latest deployment UUID
    cmd = "docker exec coolify-db psql -U coolify -d coolify -c \"SELECT deployment_uuid FROM application_deployment_queues WHERE application_id = 16 ORDER BY created_at DESC LIMIT 1;\""
    stdin, stdout, stderr = ssh.exec_command(cmd)
    print(stdout.read().decode())
    ssh.close()
except Exception as e:
    print(f"Error: {e}")
