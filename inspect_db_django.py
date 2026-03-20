from django.db import connection
import json

output = {}
with connection.cursor() as cursor:
    for table in ['bot_sessions', 'users_user', 'auth_user', 'callcenter_solicitudticket']:
        cursor.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table}'")
        output[table] = [row[0] for row in cursor.fetchall()]

with open('db_schema_output.json', 'w') as f:
    json.dump(output, f, indent=2)

print("SCHEMA_SAVED_TO_FILE")
