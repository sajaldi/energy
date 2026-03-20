import json

filepath = r'd:/Apps/energia/energy/workflow_cierre_ticket.json'
try:
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    for node in data['nodes']:
        if node.get('name') == 'Subir Foto (Django)':
            params = node['parameters']
            # Cambiar de JSON stringified a Form-Data o Binary
            params['sendBinaryData'] = True
            params['binaryPropertyName'] = "data" # Por defecto GOWA pone el binario en 'data'
            # Desactivar body json si existía
            if 'jsonBody' in params:
                del params['jsonBody']
            if 'specifyBody' in params:
                del params['specifyBody']
            if 'sendBody' in params:
                del params['sendBody']
            
            # Asegurar que el método sea POST
            params['method'] = 'POST'
            
            print(f"Node '{node['name']}' updated to send binary data.")

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("SUCCESS")
except Exception as e:
    print(f"ERROR: {e}")
