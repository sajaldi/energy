import requests
import json

API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwOTM0MjU4Ni1jN2MzLTQ2ZjEtYmE1Mi00MjE3OTBkYWU0ZmQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiZTNjYjgzMzAtMDI2NS00NDRlLTkzNDItODk1NTM4YTEzZjAxIiwiaWF0IjoxNzcyNjM0NTYxfQ.r__JBW2L7qhAz7SAtqLw7XkS4pzn_28iDTLxFgkhXWc"
BASE_URL = "http://localhost:5678/api/v1"
WORKFLOW_ID = "p4EEBCuMa0BMutVW"

headers = {
    "X-N8N-API-KEY": API_KEY,
    "Accept": "application/json",
    "Content-Type": "application/json"
}

def update_workflow():
    print(f"Fetching workflow {WORKFLOW_ID}...")
    resp = requests.get(f"{BASE_URL}/workflows/{WORKFLOW_ID}", headers=headers)
    if resp.status_code != 200:
        print(f"Error fetching: {resp.status_code} - {resp.text}")
        return
    
    wf = resp.json()
    updated = False
    
    for node in wf.get("nodes", []):
        if node.get("type") == "n8n-nodes-base.extractFromFile":
            old_version = node.get("typeVersion", 1)
            if old_version < 1.1:
                print(f"Updating node '{node['name']}' from version {old_version} to 1.1")
                node["typeVersion"] = 1.1
                updated = True
    
    if not updated:
        print("No nodes needed updating.")
        return

    print("Sending update to n8n...")
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
        print("Success! Workflow updated with newer extraction nodes.")
    else:
        print(f"Error updating: {put_resp.status_code} - {put_resp.text}")

if __name__ == "__main__":
    update_workflow()
