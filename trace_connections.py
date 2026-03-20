import json

with open('d:/Apps/energia/energy/workflow_cierre_ticket.json', encoding='utf-8') as f:
    d = json.load(f)

connections = d.get('connections', {})
source_node = 'Switch -> Cierre 2'

print(f"--- Outgoing connections from '{source_node}' ---")
if source_node in connections:
    branches = connections[source_node]
    for branch_type, results in branches.items():
        for i, targets in enumerate(results):
            print(f"Index {i}:")
            for target in targets:
                print(f"  -> {target['node']}")
