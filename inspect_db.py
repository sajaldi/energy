import psycopg2
try:
    conn = psycopg2.connect(dbname='postgres', user='postgres', password='admin123', host='127.0.0.1', port='5434')
    cur = conn.cursor()
    
    # List tables
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    tables = [row[0] for row in cur.fetchall()]
    print(f"Tables: {tables}")
    
    if 'bot_sessions' in tables:
        cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'bot_sessions'")
        print(f"bot_sessions columns: {cur.fetchall()}")
        
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
