from django.db import connection
from callcenter.models import SolicitudTicket

def run():
    cursor = connection.cursor()
    cursor.execute("SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'callcenter_solicitudticket';")
    for row in cursor.fetchall():
        print(f"{row[0]}: {row[1]}")

if __name__ == "__main__":
    run()
