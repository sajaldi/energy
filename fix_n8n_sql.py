import requests
import json

API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwOTM0MjU4Ni1jN2MzLTQ2ZjEtYmE1Mi00MjE3OTBkYWU0ZmQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiZTNjYjgzMzAtMDI2NS00NDRlLTkzNDItODk1NTM4YTEzZjAxIiwiaWF0IjoxNzcyNjM0NTYxfQ.r__JBW2L7qhAz7SAtqLw7XkS4pzn_28iDTLxFgkhXWc"
BASE_URL = "http://localhost:5678/api/v1"
WORKFLOW_ID = "p4EEBCuMa0BMutVW"
NODE_ID = "fe9e7c11-a58c-4354-9875-6393ccc5cb9e"

headers = {
    "X-N8N-API-KEY": API_KEY,
    "Accept": "application/json",
    "Content-Type": "application/json"
}

def fix_workflow():
    # 1. Fetch current workflow
    print(f"Fetching workflow {WORKFLOW_ID}...")
    resp = requests.get(f"{BASE_URL}/workflows/{WORKFLOW_ID}", headers=headers)
    if resp.status_code != 200:
        print(f"Error fetching: {resp.status_code} - {resp.text}")
        return
    
    wf = resp.json()
    
    # 2. Find and update the SQL node
    updated = False
    for node in wf.get("nodes", []):
        if node.get("id") == NODE_ID or node.get("name") == "Execute a SQL query":
            print(f"Found node: {node['name']}")
            old_query = node["parameters"].get("query", "")
            # We want to escape single quotes in the text
            # Double single quote '' is the way to escape ' in Postgres
            new_query = "UPDATE documentos_documento\nSET \n  contenido_texto = '{{ $json.texto.replaceAll(\"\'\", \"\'\'\") }}',\n  actualizado_en = NOW()\nWHERE\n  id = {{ $json.documento_id }};\n"
            
            if old_query != new_query:
                node["parameters"]["query"] = new_query
                updated = True
                print("Query updated in local object.")
            else:
                print("Query is already up to date.")
                # We still might want to force update to ensure it's active
    
    if not updated:
        print("No changes needed or node not found.")
        # Check by name if ID mismatch
        return

    # 3. Send update
    print("Sending update to n8n...")
    update_payload = {
        "name": wf["name"],
        "nodes": wf["nodes"],
        "connections": wf["connections"],
        "settings": {
            "executionOrder": "v1"
        }
    }
    
    print(f"Payload keys: {list(update_payload.keys())}")
    
    put_resp = requests.put(f"{BASE_URL}/workflows/{WORKFLOW_ID}", headers=headers, json=update_payload)
    if put_resp.status_code == 200:
        print("Success! Workflow updated and saved.")
    else:
        print(f"Error updating: {put_resp.status_code} - {put_resp.text}")

if __name__ == "__main__":
    fix_workflow()
