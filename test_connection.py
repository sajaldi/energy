import os
import socket
import psycopg
from sshtunnel import SSHTunnelForwarder

SSH_USER = 'vboxuser'
SSH_PASS = 'PasswordRoot07'
SSH_HOST = '181.115.47.107'
SSH_PORT = 3456
LOCAL_DB_PORT = 5434  # Use a different port for testing
REMOTE_DB_HOST = '10.30.1.11'
REMOTE_DB_PORT = 5432

print(f"Connecting to {SSH_HOST}...")

with SSHTunnelForwarder(
    (SSH_HOST, SSH_PORT),
    ssh_username=SSH_USER,
    ssh_password=SSH_PASS,
    remote_bind_address=(REMOTE_DB_HOST, REMOTE_DB_PORT),
    local_bind_address=('127.0.0.1', LOCAL_DB_PORT),
    set_keepalive=30.0
) as tunnel:
    print(f"Tunnel active: {tunnel.is_active}")
    if tunnel.is_active:
        print(f"Testing DB connection on localhost:{LOCAL_DB_PORT}...")
        try:
            conn = psycopg.connect(
                dbname='postgres',
                user='postgres',
                password='admin123',
                host='127.0.0.1',
                port=LOCAL_DB_PORT,
                connect_timeout=5,
                sslmode='disable'
            )
            print("✅ DB Connection SUCCESSFUL!")
            conn.close()
        except Exception as e:
            print(f"❌ DB Connection FAILED: {e}")
