from django.db import connection
from django.utils import timezone
import datetime

with connection.cursor() as cursor:
    cursor.execute("SHOW TIMEZONE")
    db_tz = cursor.fetchone()[0]
    cursor.execute("SELECT NOW(), CURRENT_TIMESTAMP, LOCALTIMESTAMP")
    db_times = cursor.fetchone()

print(f"DJANGO_TIME_ZONE_SETTING: {timezone.get_current_timezone_name()}")
print(f"DB_TIMEZONE_SETTING: {db_tz}")
print(f"DB_NOW: {db_times[0]}")
print(f"DB_CURRENT_TIMESTAMP: {db_times[1]}")
print(f"DB_LOCALTIMESTAMP: {db_times[2]}")
print(f"SYSTEM_NOW_LOCAL: {datetime.datetime.now()}")
print(f"SYSTEM_NOW_UTC: {datetime.datetime.utcnow()}")
