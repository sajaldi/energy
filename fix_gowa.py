import json

filepath = r'd:/Apps/energia/energy/workflow_cierre_ticket.json'
try:
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    updated_count = 0
    for node in data['nodes']:
        if node.get('type') == '@aldinokemal2104/n8n-nodes-gowa.gowa':
            params = node.get('parameters', {})
            # Revert phone to phoneNumber
            if 'phone' in params:
                val = params.pop('phone')
                params['phoneNumber'] = val
                updated_count += 1
            
            # Standardize telephone expression
            # Use $node["Variables"].json.telefono which is very stable in n8n
            if 'phoneNumber' in params:
                p_val = params['phoneNumber']
                if isinstance(p_val, str) and 'telefono' in p_val:
                    params['phoneNumber'] = "={{ $node[\"Variables\"].json.telefono }}"
    
    # Also check any other references to Variables node
    # Let's keep it simple for now and just fix the GOWA nodes which are the ones causing pain
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    print(f"SUCCESS: Fixed {updated_count} GOWA nodes.")
except Exception as e:
    print(f"ERROR: {e}")
