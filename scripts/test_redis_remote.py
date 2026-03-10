"""Test si Redis es alcanzable desde el servidor SSH remoto (Linux)."""
import paramiko
import socket

SSH_HOST = '181.115.47.107'
SSH_PORT = 3456
SSH_USER = 'vboxuser'
SSH_PASS = 'PasswordRoot07'

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(SSH_HOST, SSH_PORT, SSH_USER, SSH_PASS, timeout=10)

# Test 1: Docker containers en la VM
print("=== Test 1: Docker containers corriendo ===")
stdin, stdout, stderr = c.exec_command('docker ps --format "{{.Names}} {{.Ports}}" 2>/dev/null || echo "docker no disponible"')
print(stdout.read().decode())

# Test 2: Verificar si hay algo en 6379 en la VM
print("=== Test 2: Netcat a 10.30.1.11:6379 ===")
stdin, stdout, stderr = c.exec_command('timeout 3 bash -c "echo PING | nc -w 2 10.30.1.11 6379" 2>&1 || echo "FAIL: No conecta"')
print(stdout.read().decode())

# Test 3: Netcat a localhost:6379
print("=== Test 3: Netcat a 127.0.0.1:6379 ===")
stdin, stdout, stderr = c.exec_command('timeout 3 bash -c "echo PING | nc -w 2 127.0.0.1 6379" 2>&1 || echo "FAIL: No conecta"')
print(stdout.read().decode())

# Test 4: IP del sistema
print("=== Test 4: IP del sistema SSH ===")
stdin, stdout, stderr = c.exec_command('hostname -I 2>/dev/null || ipconfig 2>/dev/null | head -30')
print(stdout.read().decode())

# Test 5: Puertos escuchando
print("=== Test 5: Puertos escuchando ===")
stdin, stdout, stderr = c.exec_command('ss -tlnp 2>/dev/null | grep -E "6379|5432|9000" || netstat -tlnp 2>/dev/null | grep -E "6379|5432|9000"')
print(stdout.read().decode())

c.close()
print("Done.")
