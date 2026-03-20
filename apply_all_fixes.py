import json
import re

try:
    with open('target_workflow.json', 'r', encoding='utf-8-sig') as f:
        data = json.load(f)

    nodes = data.get('nodes', [])
    connections = data.get('connections', {})

    # 1. Fix "Filtro Anti-Loop1"
    for node in nodes:
        if node.get('name') == 'Filtro Anti-Loop1':
            conds = node.get('parameters', {}).get('conditions', {}).get('boolean', [])
            for cond in conds:
                if cond.get('value1') == '={{ $json.fromMe }}':
                    cond['value1'] = '={{ !$json.fromMe }}'
                    print("Inverted Filtro Anti-Loop1 logic.")

    # 2. Fix "Subir Foto (Django)"
    for node in nodes:
        if node.get('name') == 'Subir Foto (Django)':
            params = node.get('parameters', {})
            params['sendBody'] = True
            params['bodyContentType'] = 'multipart-form-data'
            params['sendBinaryData'] = True
            params['binaryPropertyName'] = 'data'
            # Clean existing manual body parameters if any
            if 'bodyParameters' in params:
                del params['bodyParameters']
            print("Configured Subir Foto (Django) for binary multipart.")

    # 3. Fix "Variables" (media_id path)
    for node in nodes:
        if node.get('name') == 'Variables':
            vals = node.get('parameters', {}).get('values', {}).get('string', [])
            for v in vals:
                if v.get('name') == 'media_id':
                    v['value'] = "={{ $json.body?.payload?.mediaId || $json.body?.mediaId || $json.body?.payload?.id || $json.body?.id || '' }}"
                    print("Updated media_id extraction path.")

    # 4. Reroute Logic (Connections)
    if "Switch -> Cierre 2" in connections:
        # Output 2 is FOTO/VALIDANDO
        # Connections structure: {"NodeName": {"main": [[...], [...], [...]]}}
        connections["Switch -> Cierre 2"]["main"][2] = [{"node": "Hay Foto?", "type": "main", "index": 0}]

    if "Hay Foto?" in connections:
        connections["Hay Foto?"]["main"] = [
            [{"node": "Descargar Foto (GOWA)", "type": "main", "index": 0}], # TRUE
            [{"node": "IF -> Escribió Listo?", "type": "main", "index": 0}]   # FALSE
        ]

    if "IF -> Escribió Listo?" in connections:
        connections["IF -> Escribió Listo?"]["main"] = [
            [{"node": "Set -> Confirmar", "type": "main", "index": 0}], # TRUE
            [{"node": "Hay Foto?", "type": "main", "index": 0}]         # FALSE
        ]
    print("Rerouted FOTO state logic connections.")

    # 5. SQL Syntax Fixes (Quotes)
    for node in nodes:
        if node.get('type') == 'n8n-nodes-base.postgres' or 'postgres' in node.get('type', ''):
            query = node.get('parameters', {}).get('query', '')
            if query and isinstance(query, str):
                new_query = query.replace('\\u0027', "'").replace('""', "''")
                if new_query != query:
                    node['parameters']['query'] = new_query
                    print(f"Fixed SQL syntax in node: {node.get('name')}")

    with open('target_workflow.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    print("Successfully updated target_workflow.json")

except Exception as e:
    print(f"Error: {e}")
