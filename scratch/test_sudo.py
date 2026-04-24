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
    # Test sudo with password (if needed, but usually passwordless for these users)
    cmd = 'sudo ls -la /data/coolify/ssh/logs'
    stdin, stdout, stderr = ssh.exec_command(cmd)
    print(f"Stdout: {stdout.read().decode()}")
    print(f"Stderr: {stderr.read().decode()}")
    ssh.close()
except Exception as e:
    print(f"Error: {e}")
