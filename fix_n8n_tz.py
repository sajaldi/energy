import os
import json
import re

files_to_fix = [
    'target_workflow.json',
    'workflow_cierre_ticket.json',
    'n8n/flujowhatsapp.json',
    'live_workflows.json',
    'workflow_minified.json',
    'payload.json'
]

def fix_query(query):
    if not isinstance(query, str):
        return query
    
    # 1. Fix the main pattern with INTERVAL
    # Pattern: (expression)::timestamp + INTERVAL '6 hours'
    # Replacement: (expression AT TIME ZONE 'America/Tegucigalpa')
    query = re.sub(
        r'\(([^)]+)\)::timestamp\s*\+\s*INTERVAL\s*\'6 hours\'',
        r'(\1 AT TIME ZONE \'America/Tegucigalpa\')',
        query
    )
    
    # 2. Fix the pattern without INTERVAL (manual update)
    # Pattern: (to_date(..., 'DD/MM/YYYY') + (fecha_actividades::time))::timestamp
    query = re.sub(
        r'\(to_date\(([^,]+),\s*\'DD/MM/YYYY\'\)\s*\+\s*\(fecha_actividades::time\)\)::timestamp',
        r'((to_date(\1, \'DD/MM/YYYY\') + (fecha_actividades::time)) AT TIME ZONE \'America/Tegucigalpa\')',
        query
    )
    
    query = re.sub(
        r'\(to_date\(([^,]+),\s*\'DD/MM/YYYY\'\)\s*\+\s*\(fecha_cierre::time\)\)::timestamp',
        r'((to_date(\1, \'DD/MM/YYYY\') + (fecha_cierre::time)) AT TIME ZONE \'America/Tegucigalpa\')',
        query
    )

    # 3. Handle escaped quotes in JSON strings (sometimes they use \u0027)
    query = query.replace(r"\\u00276 hours\\u0027", r"\\u0027America/Tegucigalpa\\u0027")
    
    return query

def process_node(node):
    if isinstance(node, dict):
        if 'parameters' in node and isinstance(node['parameters'], dict) and 'query' in node['parameters']:
            node['parameters']['query'] = fix_query(node['parameters']['query'])
        # Recursive for nested structures if any
    return node

for file_path in files_to_fix:
    if not os.path.exists(file_path):
        print(f"Skipping {file_path}, not found.")
        continue
    
    print(f"Processing {file_path}...")
    try:
        # Try different encodings
        content = None
        for enc in ['utf-8-sig', 'utf-8', 'latin-1']:
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    content = f.read()
                data = json.loads(content)
                print(f"  Loaded with {enc}")
                break
            except Exception:
                continue
        
        if data is None:
            print(f"  Could not load {file_path}")
            continue

        if isinstance(data, dict) and 'nodes' in data:
            data['nodes'] = [process_node(node) for node in data['nodes']]
        elif isinstance(data, list):
            data = [process_node(node) for node in data]
        elif isinstance(data, dict) and 'name' in data and 'nodes' in data: # payload.json structure
            data['nodes'] = [process_node(node) for node in data['nodes']]
            
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Successfully fixed {file_path}")
    except Exception as e:
        print(f"Error fixing {file_path}: {e}")
