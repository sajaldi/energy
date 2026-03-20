import json

filepath = r'd:/Apps/energia/energy/workflow_cierre_ticket.json'
try:
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    node = [n for n in data['nodes'] if n['name'] == 'Procesar Bloque Cierre'][0]
    
    # La lógica solicitada por el usuario:
    # fecha_cierre = HF
    # fecha_actividades = HI (Fecha de Diagnostico/Inicio)
    
    # El query actual ya tiene:
    # fecha_actividades = derivado de HI
    # fecha_cierre = derivado de HF
    
    # Sin embargo, el usuario dice: "fecha de closure necesito que sea HF y fecha de Diagnostico: HI"
    # Esto ya es lo que hace el query. 
    # Lo que voy a hacer es REFORZAR los COALESCE y asegurarme de que el ruteo de las variables sea el estandarizado.
    
    nuevo_query = """UPDATE bot_sessions 
SET status = 'CERRANDO:' || split_part(status, ':', 2) || ':VALIDANDO' 
WHERE phone_number = '{{ $node["Variables"].json.telefono }}';

UPDATE callcenter_solicitudticket 
SET 
  diagnostico = COALESCE(NULLIF(TRIM(substring($${{ $node["Variables"].json.mensaje_original }}$$ from '(?i)Diagn[oó]stico:[ ]*([^\\n\\r-]*)')), ''), $${{ $node["Variables"].json.mensaje_original }}$$ death),
  actividades = COALESCE(NULLIF(TRIM(substring($${{ $node["Variables"].json.mensaje_original }}$$ from '(?i)Acci[oó]n realizada:[ ]*([^\\n\\r-]*)')), ''), 'Ver diagnóstico'),
  fecha_actividades = COALESCE(
    (to_date(substring($${{ $node["Variables"].json.mensaje_original }}$$ from '(?i)HI:[ ]*([0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4})'), 'DD/MM/YYYY') + COALESCE(NULLIF(TRIM(substring($${{ $node["Variables"].json.mensaje_original }}$$ from '(?i)HI:[ ]*[0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4}[ ]+([0-9]{1,2}:[0-9]{2}[ ]*[a-zA-Z]*)')), '')::time, '00:00'::time))::timestamp + INTERVAL '6 hours',
    (CURRENT_DATE + NULLIF(TRIM(substring($${{ $node["Variables"].json.mensaje_original }}$$ from '(?i)HI:[ ]*([0-9]{1,2}:[0-9]{2}[ ]*[a-zA-Z]*)')), '')::time)::timestamp + INTERVAL '6 hours',
    fecha_actividades
  ),
  fecha_cierre = COALESCE(
    (to_date(substring($${{ $node["Variables"].json.mensaje_original }}$$ from '(?i)HF:[ ]*([0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4})'), 'DD/MM/YYYY') + COALESCE(NULLIF(TRIM(substring($${{ $node["Variables"].json.mensaje_original }}$$ from '(?i)HF:[ ]*[0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4}[ ]+([0-9]{1,2}:[0-9]{2}[ ]*[a-zA-Z]*)')), '')::time, '00:00'::time))::timestamp + INTERVAL '6 hours',
    (CURRENT_DATE + NULLIF(TRIM(substring($${{ $node["Variables"].json.mensaje_original }}$$ from '(?i)HF:[ ]*([0-9]{1,2}:[0-9]{2}[ ]*[a-zA-Z]*)')), '')::time)::timestamp + INTERVAL '6 hours',
    fecha_cierre
  ),
  observaciones = COALESCE(NULLIF(TRIM(substring($${{ $node["Variables"].json.mensaje_original }}$$ from '(?i)Observa[cv]iones:[ ]*([^\\n\\r-]*)')), ''), 'Ninguna') || 
                  ' | UF: ' || COALESCE(NULLIF(TRIM(substring($${{ $node["Variables"].json.mensaje_original }}$$ from '(?i)UF:[ ]*([^\\n\\r-]*)')), ''), 'N/A')
WHERE folio = split_part((SELECT status FROM bot_sessions WHERE phone_number = '{{ $node["Variables"].json.telefono }}'), ':', 2)
RETURNING 
  (fecha_cierre < fecha_actividades) as es_negativo,
  (substring($${{ $node["Variables"].json.mensaje_original }}$$ from '(?i)HI:[ ]*([^\\n\\r-]*)') NOT LIKE '%/%') as hi_sin_fecha,
  (substring($${{ $node["Variables"].json.mensaje_original }}$$ from '(?i)HF:[ ]*([^\\n\\r-]*)') NOT LIKE '%/%') as hf_sin_fecha;"""
    
    node['parameters']['query'] = nuevo_query
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("SUCCESS")
except Exception as e:
    print(f"ERROR: {e}")
