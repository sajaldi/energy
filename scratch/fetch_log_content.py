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
    # Fetch logs for deployment 562
    cmd = "docker exec coolify-db psql -U coolify -d coolify -t -c \"SELECT substring(logs from 1 for 500) FROM application_deployment_queues WHERE id = 562;\""
    stdin, stdout, stderr = ssh.exec_command(cmd)
    print(stdout.read().decode())
    ssh.close()
except Exception as e:
    print(f"Error: {e}")
