import json
import uuid

filepath = r'd:/Apps/energia/energy/workflow_cierre_ticket.json'

with open(filepath, 'r', encoding='utf-8') as f:
    data = json.load(f)

nodes = data['nodes']
connections = data['connections']

# --- STEP 1: Update 'Variables' node to capture media_id ---
for node in nodes:
    if node['name'] == 'Variables':
        values = node['parameters']['values']['string']
        # Add media_id extraction
        if not any(v['name'] == 'media_id' for v in values):
            values.append({
                'name': 'media_id',
                'value': '={{ $json.body?.payload?.id || $json.body?.id || $json.body?.payload?.mediaId || $json.body?.mediaId || "" }}'
            })
        print("Updated 'Variables' node with media_id.")

# --- STEP 2: Create 'GOWA Download' node ---
gowa_download_node = {
    "parameters": {
        "operation": "download", # Assuming this is the operation
        "messageId": "={{ $node[\"Variables\"].json.media_id }}",
        "binaryPropertyName": "data"
    },
    "id": str(uuid.uuid4()),
    "name": "Descargar Foto (GOWA)",
    "type": "@aldinokemal2104/n8n-nodes-gowa.gowa",
    "typeVersion": 1,
    "position": [
        -5300, # Between IF and Subir Foto
        6100
    ],
    "credentials": {
        "goWhatsappApi": {
            "id": "3ZCyhP63fGLpPiQN", # Use same credential from Msg Foto
            "name": "GOWA account"
        }
    }
}
nodes.append(gowa_download_node)
print("Created 'GOWA Download' node.")

# --- STEP 3: Update connections to insert the Download node ---
# IF -> Escribió Listo? -> index 1 connects to Subir Foto
if 'IF -> Escribió Listo?' in connections:
    branches = connections['IF -> Escribió Listo?']['main']
    # branches[1] is the FALSE branch (where photos go)
    # It currently connects to 'Subir Foto (Django)'
    old_targets = branches[1]
    branches[1] = [{
        "node": "Descargar Foto (GOWA)",
        "type": "main",
        "index": 0
    }]
    # Now connect Download node to Subir Foto
    connections['Descargar Foto (GOWA)'] = {
        "main": [
            old_targets
        ]
    }
    print("Injected 'GOWA Download' into connections.")

# --- STEP 4: Create Code node for parsing message ('Parsear Bloque Cierre') ---
code_js = """
const msg = $node["Variables"].json.mensaje_original || "";

function extract(regex, defaultVal = "") {
  const match = msg.match(regex);
  return (match && match[1]) ? match[1].trim() : defaultVal;
}

// Regex more robust as suggested by user
const diagnostico = extract(/Diagn[oó]stico:[ ]*([^\n\r-]+)/i, msg);
const actividades = extract(/Acci[oó]n realizada:[ ]*([^\n\r-]+)/i, "Ver diagnóstico");
const hi_str = extract(/HI:[ ]*([^\n\r-]+)/i, "");
const hf_str = extract(/HF:[ ]*([^\n\r-]+)/i, "");
const observaciones = extract(/Observa[cv]iones:[ ]*([^\n\r-]+)/i, "Ninguna");
const uf = extract(/UF:[ ]*([^\n\r-]+)/i, "N/A");

return {
  diagnostico,
  actividades,
  hi_str,
  hf_str,
  observaciones,
  uf
};
"""

parsing_code_node = {
    "parameters": {
        "jsCode": code_js
    },
    "id": str(uuid.uuid4()),
    "name": "Parsear Bloque Cierre",
    "type": "n8n-nodes-base.code",
    "typeVersion": 1,
    "position": [
        -5500, # Before Postgres
        5300
    ]
}
nodes.append(parsing_code_node)
print("Created 'Parsear Bloque Cierre' Code node.")

# --- STEP 5: Update connections for Parsing node ---
# Switch -> Cierre 1 -> index 0 connects to Procesar Bloque Cierre
if 'Switch -> Cierre 1' in connections:
    branches = connections['Switch -> Cierre 1']['main']
    old_targets_postgres = branches[0]
    branches[0] = [{
        "node": "Parsear Bloque Cierre",
        "type": "main",
        "index": 0
    }]
    # Now connect Code node to Postgres node
    connections['Parsear Bloque Cierre'] = {
        "main": [
            old_targets_postgres
        ]
    }
    print("Injected 'Parsear Bloque Cierre' into connections.")

# --- STEP 6: Update Postgres queries in 'Procesar Bloque Cierre' ---
# It will use the fields from the Code node
new_query = """
UPDATE bot_sessions 
SET status = 'CERRANDO:' || split_part(status, ':', 2) || ':VALIDANDO' 
WHERE phone_number = '{{ $node["Variables"].json.telefono }}';

UPDATE callcenter_solicitudticket 
SET 
  diagnostico = $${{ $node["Parsear Bloque Cierre"].json.diagnostico }}$$,
  actividades = $${{ $node["Parsear Bloque Cierre"].json.actividades }}$$,
  fecha_actividades = COALESCE(
    -- Try full date from HI
    (to_date(substring($${{ $node["Parsear Bloque Cierre"].json.hi_str }}$$ from '([0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4})'), 'DD/MM/YYYY') + 
     COALESCE(NULLIF(TRIM(substring($${{ $node["Parsear Bloque Cierre"].json.hi_str }}$$ from '([0-9]{1,2}:[0-9]{2}[ ]*[a-zA-Z]*)')), '')::time, '00:00'::time))::timestamp + INTERVAL '6 hours',
    -- fallback to today if only time provided
    (CURRENT_DATE + NULLIF(TRIM(substring($${{ $node["Parsear Bloque Cierre"].json.hi_str }}$$ from '([0-9]{1,2}:[0-9]{2}[ ]*[a-zA-Z]*)')), '')::time)::timestamp + INTERVAL '6 hours',
    fecha_actividades
  ),
  fecha_cierre = COALESCE(
    -- Try full date from HF
    (to_date(substring($${{ $node["Parsear Bloque Cierre"].json.hf_str }}$$ from '([0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4})'), 'DD/MM/YYYY') + 
     COALESCE(NULLIF(TRIM(substring($${{ $node["Parsear Bloque Cierre"].json.hf_str }}$$ from '([0-9]{1,2}:[0-9]{2}[ ]*[a-zA-Z]*)')), '')::time, '00:00'::time))::timestamp + INTERVAL '6 hours',
    -- fallback to today if only time provided
    (CURRENT_DATE + NULLIF(TRIM(substring($${{ $node["Parsear Bloque Cierre"].json.hf_str }}$$ from '([0-9]{1,2}:[0-9]{2}[ ]*[a-zA-Z]*)')), '')::time)::timestamp + INTERVAL '6 hours',
    fecha_cierre
  ),
  observaciones = $${{ $node["Parsear Bloque Cierre"].json.observaciones }}$$ || ' | UF: ' || $${{ $node["Parsear Bloque Cierre"].json.uf }}$$
WHERE folio = split_part((SELECT status FROM bot_sessions WHERE phone_number = '{{ $node["Variables"].json.telefono }}'), ':', 2)
RETURNING 
  (fecha_cierre < fecha_actividades) as es_negativo,
  ($${{ $node["Parsear Bloque Cierre"].json.hi_str }}$$ NOT LIKE '%/%') as hi_sin_fecha,
  ($${{ $node["Parsear Bloque Cierre"].json.hf_str }}$$ NOT LIKE '%/%') as hf_sin_fecha;
""".strip()

for node in nodes:
    if node['name'] == 'Procesar Bloque Cierre':
        node['parameters']['query'] = new_query
        print("Updated 'Procesar Bloque Cierre' with robust query using Code node data.")

# --- Save final workflow ---
with open(filepath, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print("SUCCESS: Workflow fully refactored and optimized.")
