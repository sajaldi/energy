import json

filepath = r'd:/Apps/energia/energy/workflow_cierre_ticket.json'
try:
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    def fix_expression(expr):
        if not isinstance(expr, str) or not expr.startswith('='):
            return expr
        
        # Standardize references to the node named "Variables"
        # n8n handles node names in brackets better for many cases
        old_refs = [
            "$('Variables').item.json.",
            "$('Variables').json.",
            "$(Variables).json.",
            "$(\"Variables\").json."
        ]
        new_ref = "$node[\"Variables\"].json."
        
        for old in old_refs:
            expr = expr.replace(old, new_ref)
        
        return expr

    for node in data['nodes']:
        params = node.get('parameters', {})
        # GOWA nodes special fix (phoneNumber)
        if node.get('type') == '@aldinokemal2104/n8n-nodes-gowa.gowa':
            # ensure no 'phone' key exists and phoneNumber is the one
            if 'phone' in params:
                val = params.pop('phone')
                params['phoneNumber'] = val
        
        # Recursively update expressions
        def update_params(d):
            if isinstance(d, dict):
                for k, v in d.items():
                    if isinstance(v, str):
                        d[k] = fix_expression(v)
                    else:
                        update_params(v)
            elif isinstance(d, list):
                for i in range(len(d)):
                    if isinstance(d[i], str):
                        d[i] = fix_expression(d[i])
                    else:
                        update_params(d[i])
        
        update_params(params)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    print(f"SUCCESS: Stabilized all node expressions and names.")
except Exception as e:
    print(f"ERROR: {e}")
