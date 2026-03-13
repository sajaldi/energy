import requests
import json

API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwOTM0MjU4Ni1jN2MzLTQ2ZjEtYmE1Mi00MjE3OTBkYWU0ZmQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiZTNjYjgzMzAtMDI2NS00NDRlLTkzNDItODk1NTM4YTEzZjAxIiwiaWF0IjoxNzcyNjM0NTYxfQ.r__JBW2L7qhAz7SAtqLw7XkS4pzn_28iDTLxFgkhXWc"
BASE_URL = "http://localhost:5678/api/v1"
WORKFLOW_ID = "5ce6GPu5y6lMVRuw"

headers = {
    "X-N8N-API-KEY": API_KEY,
    "Accept": "application/json",
    "Content-Type": "application/json"
}

def fix_memory():
    # 1. Fetch current workflow
    print(f"Fetching workflow {WORKFLOW_ID}...")
    resp = requests.get(f"{BASE_URL}/workflows/{WORKFLOW_ID}", headers=headers)
    if resp.status_code != 200:
        print(f"Error fetching: {resp.status_code} - {resp.text}")
        return
    
    wf = resp.json()
    
    # 2. Fix JS Code Node to pass biblioteca_id
    js_node = next((n for n in wf["nodes"] if n["name"] == "Code in JavaScript"), None)
    if js_node:
        print("Modifying JS node to propagate biblioteca_id...")
        old_code = js_node["parameters"]["jsCode"]
        if "biblioteca_id: body.biblioteca_id" not in old_code:
            # Replace the return statement
            new_code = old_code.replace(
                "return { texto_redactado: texto_para_ia };",
                "return { texto_redactado: texto_para_ia, biblioteca_id: body.biblioteca_id };"
            )
            js_node["parameters"]["jsCode"] = new_code

    # 3. Fix Postgres Chat Memory session ID expression
    memory_node = next((n for n in wf["nodes"] if n.get("type") == "@n8n/n8n-nodes-langchain.memoryPostgresChat"), None)
    if memory_node:
        print("Updating Memory node sessionId expression...")
        memory_node["parameters"]["sessionId"] = "={{ $json.biblioteca_id || 'default' }}"

    # 4. Send update
    print("Updating workflow...")
    update_payload = {
        "name": wf["name"],
        "nodes": wf["nodes"],
        "connections": wf["connections"],
        "settings": {
            "executionOrder": "v1"
        }
    }
    
    put_resp = requests.put(f"{BASE_URL}/workflows/{WORKFLOW_ID}", headers=headers, json=update_payload)
    if put_resp.status_code == 200:
        print("Success! Workflow fixed.")
    else:
        print(f"Error updating: {put_resp.status_code} - {put_resp.text}")

if __name__ == "__main__":
    fix_memory()
