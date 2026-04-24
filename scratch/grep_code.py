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
    # Search for log path in the code
    cmd = 'docker exec coolify grep -r "storage_path" /var/www/html/app | grep "logs" | head -n 10'
    stdin, stdout, stderr = ssh.exec_command(cmd)
    print(stdout.read().decode())
    ssh.close()
except Exception as e:
    print(f"Error: {e}")
