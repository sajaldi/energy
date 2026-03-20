import json
import subprocess

wf_id = "mNnJ3JL47Qn4sVkM"
api_apiKey = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwOTM0MjU4Ni1jN2MzLTQ2ZjEtYmE1Mi00MjE3OTBkYWU0ZmQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiMjgzODliZjYtZGQxMC00NWIxLWI4ODAtZTJmMjA3ODIzNzhjIiwiaWF0IjoxNzczODQ1OTQ0fQ.13ueEws9HHdUdiO8ejyHSZsebjnuG_PSIzvmzcFzQrk"
url = f"http://181.115.47.107:5678/api/v1/workflows/{wf_id}"

with open('target_workflow.json', 'r', encoding='utf-8-sig') as f:
    data = json.load(f)

# 1. Purify Nodes
purified_nodes = []
for node in data.get('nodes', []):
    p_node = {
        "name": node.get("name"),
        "type": node.get("type"),
        "typeVersion": node.get("typeVersion"),
        "position": node.get("position"),
        "parameters": node.get("parameters")
    }
    if node.get("credentials"):
        p_node["credentials"] = node.get("credentials")
    purified_nodes.append(p_node)

# 2. Purify Connections
# Connections: { "NodeName": { "main": [ [ {"node": "Target", "type": "main", "index": 0} ] ] } }
purified_connections = {}
for source_node, outputs in data.get('connections', {}).items():
    purified_connections[source_node] = {}
    for output_type, indices in outputs.items():
        purified_connections[source_node][output_type] = []
        for index_group in indices:
            p_group = []
            for conn in index_group:
                p_conn = {
                    "node": conn.get("node"),
                    "index": conn.get("index") or 0
                }
                # Omit "type": "main" inside the connection object if possible
                p_group.append(p_conn)
            purified_connections[source_node][output_type].append(p_group)

payload = {
    "name": data.get("name"),
    "nodes": purified_nodes,
    "connections": purified_connections
}

with open('payload.json', 'w', encoding='utf-8') as f:
    json.dump(payload, f)

cmd = [
    "curl.exe", "-X", "PUT", url,
    "-H", f"X-N8N-API-KEY: {api_apiKey}",
    "-H", "Content-Type: application/json",
    "-d", "@payload.json"
]

result = subprocess.run(cmd, capture_output=True, text=True)
print(f"STDOUT: {result.stdout}")
print(f"STDERR: {result.stderr}")
