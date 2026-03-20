from django.db import connection
import json

output = {}
with connection.cursor() as cursor:
    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    tables = [row[0] for row in cursor.fetchall()]
    
    for table in tables:
        cursor.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table}'")
        cols = [row[0] for row in cursor.fetchall()]
        if any('phone' in c.lower() for c in cols) or any('tel' in c.lower() for c in cols):
            output[table] = cols

with open('phone_tables.json', 'w') as f:
    json.dump(output, f, indent=2)

print("PHONE_TABLES_SAVED")
