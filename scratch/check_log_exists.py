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
    cmd = "docker exec coolify-db psql -U coolify -d coolify -t -c \"SELECT deployment_uuid FROM application_deployment_queues WHERE application_id = 16 ORDER BY id DESC LIMIT 1;\""
    stdin, stdout, stderr = ssh.exec_command(cmd)
    uuid = stdout.read().decode().strip()
    print(f"UUID: {uuid}")
    
    if uuid:
        # Check if log file exists
        cmd = f"ls -l /data/coolify/ssh/logs/{uuid}.log"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        print(f"Log file status: {stdout.read().decode()} {stderr.read().decode()}")
        
    ssh.close()
except Exception as e:
    print(f"Error: {e}")
