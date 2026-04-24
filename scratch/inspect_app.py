import os
import sys
import django
import json

# Add project root to path
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from core.utils_ssh import get_ssh_client

try:
    ssh = get_ssh_client()
    # Check labels of a specific app principal
    # I'll use a wildcard to find the container name that starts with the ID I saw
    cmd = "docker ps --filter 'label=coolify.serviceName=app-principal-softcom' --format '{{.Names}}' | head -n 1"
    stdin, stdout, stderr = ssh.exec_command(cmd)
    container_name = stdout.read().decode().strip()
    
    if container_name:
        print(f"Inspecting {container_name}...")
        cmd = f"docker inspect {container_name} --format '{{{{json .Config.Labels}}}}'"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        labels = json.loads(stdout.read().decode())
        print(json.dumps(labels, indent=2))
    else:
        print("Container not found.")
    ssh.close()
except Exception as e:
    print(f"Error: {e}")
