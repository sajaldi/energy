import json

filepath = r'd:/Apps/energia/energy/workflow_cierre_ticket.json'
try:
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    def fix_all_expressions(expr):
        if not isinstance(expr, str) or not expr.startswith('='):
            return expr
        
        # Comprehensive replacement of old-style references
        # Change $(Node Name).json or $('Node Name').item.json
        # to $node["Node Name"].json
        
        # Handle the .item.json pattern
        import re
        # Pattern: $(...) or $('...') or $("...") followed by .item.json
        expr = re.sub(r"\$\(['\"]?([^'\"()]+)['\"]?\)\.item\.json", r'$node["\1"].json', expr)
        # Handle the simple .json pattern
        expr = re.sub(r"\$\(['\"]?([^'\"()]+)['\"]?\)\.json", r'$node["\1"].json', expr)
        
        return expr

    def recurse_params(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str):
                    obj[k] = fix_all_expressions(v)
                else:
                    recurse_params(v)
        elif isinstance(obj, list):
            for i in range(len(obj)):
                if isinstance(obj[i], str):
                    obj[i] = fix_all_expressions(obj[i])
                else:
                    recurse_params(obj[i])

    for node in data['nodes']:
        recurse_params(node.get('parameters', {}))
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("SUCCESS: Normalized all expressions to $node syntax.")
except Exception as e:
    print(f"ERROR: {e}")
