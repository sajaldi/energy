import time
import sys
import os
from sshtunnel import SSHTunnelForwarder
import logging

# Configuración del Túnel (Basada en tus settings de Django)
SSH_HOST = '181.115.47.107'
SSH_PORT = 3456
SSH_USER = 'vboxuser'
SSH_PASS = 'PasswordRoot07'
REMOTE_DB_HOST = '10.30.1.11'
REMOTE_DB_PORT = 5432
LOCAL_DB_PORT = 5434

def start_tunnel():
    print("==========================================")
    print("      SOFTCOM - DB TUNNEL MANAGER         ")
    print("==========================================")
    print(f"SSH Host:     {SSH_HOST}:{SSH_PORT}")
    print(f"Remote DB:    {REMOTE_DB_HOST}:{REMOTE_DB_PORT}")
    print(f"Local Port:   127.0.0.1:{LOCAL_DB_PORT}")
    print("------------------------------------------")

    while True:
        try:
            print(f"[{time.strftime('%H:%M:%S')}] Intentando conectar...")
            
            with SSHTunnelForwarder(
                (SSH_HOST, SSH_PORT),
                ssh_username=SSH_USER,
                ssh_password=SSH_PASS,
                remote_bind_address=(REMOTE_DB_HOST, REMOTE_DB_PORT),
                local_bind_address=('127.0.0.1', LOCAL_DB_PORT),
                set_keepalive=30.0
            ) as tunnel:
                print(f"[{time.strftime('%H:%M:%S')}] ✅ TÚNEL ACTIVO!")
                print(">>> Puedes usar la base de datos en localhost:5434")
                print(">>> Presiona Ctrl+C para cerrar.")
                
                while tunnel.is_active:
                    time.sleep(5)
                    
        except KeyboardInterrupt:
            print("\nCerrando túnel por petición del usuario...")
            break
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] ❌ ERROR: {e}")
            print("Reintentando en 5 segundos...")
            time.sleep(5)

if __name__ == "__main__":
    # Desactivar logs innecesarios de sshtunnel para una consola limpia
    logging.getLogger('sshtunnel').setLevel(logging.CRITICAL)
    start_tunnel()
