import json
import collections

filepath = r'd:/Apps/energia/energy/workflow_cierre_ticket.json'
with open(filepath, 'r', encoding='utf-8') as f:
    data = json.load(f)

nodes = data['nodes']
connections = data['connections']

node_names = set(n['name'] for n in nodes)
node_ids = set(n['id'] for n in nodes)

print(f"Total Nodes: {len(nodes)}")
print(f"Unique Names: {len(node_names)}")
print(f"Unique IDs: {len(node_ids)}")

if len(nodes) != len(node_ids):
    ids = [n['id'] for n in nodes]
    dupes = [item for item, count in collections.Counter(ids).items() if count > 1]
    print(f"DUPLICATE IDs FOUND: {dupes}")

if len(nodes) != len(node_names):
    names = [n['name'] for n in nodes]
    dupes = [item for item, count in collections.Counter(names).items() if count > 1]
    print(f"DUPLICATE NAMES FOUND: {dupes}")

# Check connections
for source, targets in connections.items():
    if source not in node_names:
        print(f"CONNECTION ERROR: Source node '{source}' does not exist in nodes list.")
    
    for type_name, branches in targets.items():
        for branch in branches:
            for target in branch:
                if target['node'] not in node_names:
                    print(f"CONNECTION ERROR: Target node '{target['node']}' (linked from '{source}') does not exist.")

print("Check finished.")
