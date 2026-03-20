import sqlite3

def check_db():
    conn = sqlite3.connect('db.sqlite3')
    cursor = conn.cursor()
    
    # Check tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Tables:", [t[0] for t in tables])
    
    # Check core_perfilusuario columns
    try:
        cursor.execute("PRAGMA table_info(core_perfilusuario);")
        print("core_perfilusuario columns:", [c[1] for c in cursor.fetchall()])
    except Exception as e:
        print("Error checking core_perfilusuario:", e)
        
    # Check auth_user columns
    try:
        cursor.execute("PRAGMA table_info(auth_user);")
        print("auth_user columns:", [c[1] for c in cursor.fetchall()])
    except Exception as e:
        print("Error checking auth_user:", e)
        
    conn.close()

if __name__ == "__main__":
    check_db()
