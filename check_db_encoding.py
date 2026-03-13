import os
import django
from django.db import connection

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

def check_db_encoding():
    with connection.cursor() as cursor:
        cursor.execute("SHOW SERVER_ENCODING;")
        server_enc = cursor.fetchone()[0]
        cursor.execute("SHOW CLIENT_ENCODING;")
        client_enc = cursor.fetchone()[0]
        cursor.execute("SELECT pg_encoding_to_char(encoding) FROM pg_database WHERE datname = current_database();")
        db_enc = cursor.fetchone()[0]
        
        print(f"Server Encoding: {server_enc}")
        print(f"Client Encoding: {client_enc}")
        print(f"Database Encoding: {db_enc}")

if __name__ == "__main__":
    check_db_encoding()
