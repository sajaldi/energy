import psycopg2
try:
    conn = psycopg2.connect("postgresql://root:21b777a82860b8ab6eeebc8f@10.30.1.11:5432/energia")
    cur = conn.cursor()
    cur.execute("""
SELECT 
  (to_date(substring($$
-Diagnóstico: Prueba de diagnostico
-Acción realizada: Se realizó una acción
-HI: 16/03/2026 10:00 am
-HF: 16/03/2026 11:00 am
-UF: CBC
-Observaciones: Todo queda muy bien
$$ from '(?i)HI:[ ]*([0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4})'), 'DD/MM/YYYY') + NULLIF(TRIM(substring($$
-Diagnóstico: Prueba de diagnostico
-Acción realizada: Se realizó una acción
-HI: 16/03/2026 10:00 am
-HF: 16/03/2026 11:00 am
-UF: CBC
-Observaciones: Todo queda muy bien
$$ from '(?i)HI:[ ]*[0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4}[ ]+([0-9]{1,2}:[0-9]{2}[ ]*[a-zA-Z]*)')), '')::time)::timestamp + INTERVAL '6 hours'
    """)
    print("RES1:", cur.fetchall())
except Exception as e:
    print("ERROR:", e)
