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
    # Check application_deployment_queues
    cmd = "docker exec coolify-db psql -U coolify -d coolify -c \"SELECT id, application_id, status, created_at FROM application_deployment_queues ORDER BY created_at DESC LIMIT 5;\""
    stdin, stdout, stderr = ssh.exec_command(cmd)
    print(stdout.read().decode())
    ssh.close()
except Exception as e:
    print(f"Error: {e}")
