import time
import sys
import os
import threading
import socket
import paramiko
import logging
import subprocess
import webbrowser
from sshtunnel import SSHTunnelForwarder

# Configuración SSH
SSH_HOST = '181.115.47.107'
SSH_PORT = 3456
SSH_USER = 'vboxuser'
SSH_PASS = 'PasswordRoot07'

# IPs y Puertos
VM_IP = '10.30.1.11'
REDIS_HOST = '127.0.0.1' # Probar loopback remoto si la IP de la VM falla
LOCAL_IP = '127.0.0.1'

# Forward (Local -> Remoto)
DB_REMOTE, DB_LOCAL = 5432, 5434
N8N_REMOTE, N8N_LOCAL = 5678, 5678
APP_REMOTE, APP_LOCAL = 8070, 8070
MINIO_REMOTE, MINIO_LOCAL = 9000, 9000
MINIO_CONSOLE_REMOTE, MINIO_CONSOLE_LOCAL = 9001, 9001
REDIS_REMOTE, REDIS_LOCAL = 6379, 6379

# Reverse (Remoto -> Local)
REV_REMOTE = 9001
REV_LOCAL  = 8000  # Tu Django local

def start_celery_worker():
    """Lanza el worker de Celery usando el entorno local"""
    print(f"[{time.strftime('%H:%M:%S')}] ⚙️ Iniciando Celery Worker...")
    
    # Intentar encontrar el python del entorno virtual
    cwd = os.getcwd()
    python_exe = os.path.join(cwd, 'env', 'Scripts', 'python.exe')
    
    if not os.path.exists(python_exe):
        # Si no está en env/Scripts (ej: linux o config distinta), probar 'python'
        python_exe = 'python'
        
    cmd = [
        python_exe, "-m", "celery", 
        "-A", "energia", "worker", 
        "--loglevel=info", "-P", "solo"
    ]
    
    try:
        # Abrir en una nueva ventana de consola (solo Windows)
        if sys.platform == "win32":
            subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen(cmd)
        print(f"[{time.strftime('%H:%M:%S')}] ✅ Celery disparado en nueva ventana.")
    except Exception as e:
        print(f"❌ Error al iniciar Celery: {e}")

def handler(chan, host, port):
    sock = socket.socket()
    try:
        sock.connect((host, port))
    except Exception:
        return

    def pipe(src, dst):
        try:
            while True:
                data = src.recv(4096)
                if not data: break
                dst.send(data)
        except: pass
        finally:
            src.close()
            dst.close()

    threading.Thread(target=pipe, args=(chan, sock), daemon=True).start()
    threading.Thread(target=pipe, args=(sock, chan), daemon=True).start()

def reverse_forward_tunnel(server_port, remote_host, remote_port, transport):
    try:
        transport.request_port_forward("127.0.0.1", server_port)
    except Exception as e:
        print(f"❌ Error pidiendo Forward al servidor: {e}")
        return

    while True:
        chan = transport.accept(1000)
        if chan is None:
            continue
        threading.Thread(target=handler, args=(chan, remote_host, remote_port), daemon=True).start()

def start_tunnel():
    print("==========================================")
    print("      SOFTCOM - ULTIMATE TUNNEL V11       ")
    print("     (REDIS + AUTO-CELERY ENABLED)        ")
    print("==========================================")
    
    first_run = True

    while True:
        try:
            print(f"[{time.strftime('%H:%M:%S')}] Conectando SSH...")
            
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(SSH_HOST, SSH_PORT, SSH_USER, SSH_PASS, timeout=10)
            
            # Puente netsh en el servidor físico
            client.exec_command(f"netsh interface portproxy delete v4tov4 listenport={REV_REMOTE} listenaddress=0.0.0.0")
            client.exec_command(f"netsh interface portproxy add v4tov4 listenport={REV_REMOTE} listenaddress=0.0.0.0 connectport={REV_REMOTE} connectaddress=127.0.0.1")
            
            transport = client.get_transport()
            
            # Túnel Reverso manual
            rev_thread = threading.Thread(
                target=reverse_forward_tunnel, 
                args=(REV_REMOTE, LOCAL_IP, REV_LOCAL, transport), 
                daemon=True
            )
            rev_thread.start()

            # Forwards de salida
            with SSHTunnelForwarder(
                (SSH_HOST, SSH_PORT),
                ssh_username=SSH_USER,
                ssh_password=SSH_PASS,
                remote_bind_addresses=[
                    (VM_IP, DB_REMOTE), 
                    (VM_IP, N8N_REMOTE), 
                    (VM_IP, APP_REMOTE),
                    (VM_IP, MINIO_REMOTE),
                    (VM_IP, MINIO_CONSOLE_REMOTE),
                    (REDIS_HOST, REDIS_REMOTE)
                ],
                local_bind_addresses=[
                    (LOCAL_IP, DB_LOCAL), 
                    (LOCAL_IP, N8N_LOCAL), 
                    (LOCAL_IP, APP_LOCAL),
                    (LOCAL_IP, MINIO_LOCAL),
                    (LOCAL_IP, MINIO_CONSOLE_LOCAL),
                    (LOCAL_IP, REDIS_LOCAL)
                ],
                set_keepalive=30.0
            ) as tunnel:
                print(f"[{time.strftime('%H:%M:%S')}] ✅ CONEXIÓN EXITOSA")
                print(f"› DB:       localhost:{DB_LOCAL}")
                print(f"› MinIO:    http://localhost:{MINIO_LOCAL} (API)")
                print(f"› Redis:    localhost:{REDIS_LOCAL} (Coolify)")
                print(f"› Web 8070: http://localhost:{APP_LOCAL}")
                print(f"› CALLBACK: {SSH_HOST}:{REV_REMOTE} -> L:8000")
                
                # Iniciar Celery automáticamente al conectar el túnel
                if first_run:
                    start_celery_worker()
                    first_run = False
                
                print("==========================================")
                print("Presione Ctrl+C para cerrar el túnel")
                
                while tunnel.is_active:
                    time.sleep(5)
            
            client.close()
                    
        except KeyboardInterrupt:
            print("\nCerrando túnel...")
            break
        except Exception as e:
            print(f"❌ ERROR: {e}")
            time.sleep(5)

if __name__ == "__main__":
    logging.getLogger('sshtunnel').setLevel(logging.CRITICAL)
    start_tunnel()
