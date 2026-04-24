import os
import sys

# Add project root to path to import core
sys.path.append(os.getcwd())

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from core.utils_ssh import get_ssh_client

try:
    ssh = get_ssh_client()
    stdin, stdout, stderr = ssh.exec_command('docker ps --format "{{.Names}}|{{.Labels}}"')
    output = stdout.read().decode('utf-8')
    with open('d:\\Apps\\energia\\energy\\scratch\\labels_output.txt', 'w', encoding='utf-8') as f:
        f.write(output)
    print("Output saved to labels_output.txt")
    ssh.close()
except Exception as e:
    print(f"Error: {e}")
