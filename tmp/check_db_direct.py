import os
import django
import sys
import sqlite3

# Try to check bot_sessions in the database
# We need to know where bot_sessions table is. 
# The n8n workflow uses Postgres, so it must be in the Postgres DB.

def check_postgres():
    import psycopg2
    try:
        conn = psycopg2.connect(
            dbname="postgres",
            user="postgres",
            password="admin123",
            host="127.0.0.1",
            port="5434"
        )
        cur = conn.cursor()
        
        # Check bot_sessions
        cur.execute("SELECT * FROM bot_sessions ORDER BY last_update DESC LIMIT 5;")
        rows = cur.fetchall()
        print("Recent bot_sessions:")
        for r in rows:
            print(r)
            
        # Check recent EvidenciaTicket
        cur.execute("""
            SELECT E.id, E.descripcion, E.archivo, T.folio 
            FROM callcenter_evidenciaticket E 
            JOIN callcenter_solicitudticket T ON E.ticket_id = T.id 
            ORDER BY E.fecha_carga DESC LIMIT 10;
        """)
        evs = cur.fetchall()
        print("\nRecent Evidencias:")
        for ev in evs:
            print(ev)
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Postgres Error: {e}")

if __name__ == "__main__":
    check_postgres()
