import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "energia.settings")
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT column_name, is_nullable, column_default, data_type
        FROM information_schema.columns 
        WHERE table_name = 'activos_ubicacion' 
        ORDER BY ordinal_position
    """)
    rows = cursor.fetchall()
    for r in rows:
        print(r)
