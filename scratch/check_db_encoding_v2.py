import os
import django
from django.db import connection

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

with connection.cursor() as cursor:
    cursor.execute("SHOW server_encoding")
    server = cursor.fetchone()
    cursor.execute("SHOW client_encoding")
    client = cursor.fetchone()
    print(f"Server Encoding: {server}")
    print(f"Client Encoding: {client}")
