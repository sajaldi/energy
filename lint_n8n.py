import json

filepath = r'd:/Apps/energia/energy/workflow_cierre_ticket.json'
with open(filepath, 'r', encoding='utf-8') as f:
    data = json.load(f)

nodes = data.get('nodes', [])
connections = data.get('connections', {})

def check_obj(obj, path=""):
    if obj is None:
        print(f"LINT: Found None at {path}")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            check_obj(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            check_obj(v, f"{path}[{i}]")

# check_obj(data) # Too verbose if many None (but shouldn't be anyway)

for i, node in enumerate(nodes):
    if 'name' not in node: print(f"Node {i} missing name")
    if 'type' not in node: print(f"Node {i} missing type")
    if 'id' not in node: print(f"Node {i} missing id")
    if 'position' not in node: print(f"Node {i} missing position")
    if 'parameters' not in node: print(f"Node {node.get('name')} missing parameters")

for node_name, conn in connections.items():
    if 'main' not in conn:
        print(f"Connection for '{node_name}' missing 'main'")
    else:
        for branch_idx, branch in enumerate(conn['main']):
            for target_idx, target in enumerate(branch):
                if 'node' not in target: print(f"Target {target_idx} in branch {branch_idx} of '{node_name}' missing 'node'")
                if 'type' not in target: print(f"Target {target_idx} in branch {branch_idx} of '{node_name}' missing 'type'")
                if 'index' not in target: print(f"Target {target_idx} in branch {branch_idx} of '{node_name}' missing 'index'")

print("Lint complete.")
