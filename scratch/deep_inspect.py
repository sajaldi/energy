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
    # List all files in logs recursively
    cmd = 'find /data/coolify/ssh/logs -type f | tail -n 10'
    stdin, stdout, stderr = ssh.exec_command(cmd)
    print(f"Files in /data/coolify/ssh/logs:\n{stdout.read().decode()}")
    
    # Check coolify container logs for clues
    cmd = 'docker logs --tail 100 coolify'
    stdin, stdout, stderr = ssh.exec_command(cmd)
    # print(f"Coolify container logs:\n{stdout.read().decode()}")
    
    ssh.close()
except Exception as e:
    print(f"Error: {e}")
