import requests
import json
import uuid

API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwOTM0MjU4Ni1jN2MzLTQ2ZjEtYmE1Mi00MjE3OTBkYWU0ZmQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiZTNjYjgzMzAtMDI2NS00NDRlLTkzNDItODk1NTM4YTEzZjAxIiwiaWF0IjoxNzcyNjM0NTYxfQ.r__JBW2L7qhAz7SAtqLw7XkS4pzn_28iDTLxFgkhXWc"
BASE_URL = "http://localhost:5678/api/v1"
WORKFLOW_ID = "5ce6GPu5y6lMVRuw"
POSTGRES_CRED_ID = "0GI4GAGRXkWfR6pK"

headers = {
    "X-N8N-API-KEY": API_KEY,
    "Accept": "application/json",
    "Content-Type": "application/json"
}

def add_memory():
    # 1. Fetch current workflow
    print(f"Fetching workflow {WORKFLOW_ID}...")
    resp = requests.get(f"{BASE_URL}/workflows/{WORKFLOW_ID}", headers=headers)
    if resp.status_code != 200:
        print(f"Error fetching: {resp.status_code} - {resp.text}")
        return
    
    wf = resp.json()
    
    # 2. Check if memory already exists
    if any(n["type"] == "@n8n/n8n-nodes-langchain.memoryPostgresChat" for n in wf["nodes"]):
        print("Memory node already exists. Skipping.")
        return

    # 3. Create Memory Node
    memory_node_id = str(uuid.uuid4())
    memory_node = {
        "parameters": {
            "tableName": "agent_memory",
            "sessionId": "={{ $('Webhook').item.json.body.biblioteca_id || 'default' }}"
        },
        "id": memory_node_id,
        "name": "Postgres Chat Memory",
        "type": "@n8n/n8n-nodes-langchain.memoryPostgresChat",
        "typeVersion": 1.1,
        "position": [
            560,
            160
        ],
        "credentials": {
            "postgres": {
                "id": POSTGRES_CRED_ID,
                "name": "Postgres account"
            }
        }
    }
    
    # 4. Find AI Agent Node
    agent_node = next((n for n in wf["nodes"] if n["name"] == "AI Agent"), None)
    if not agent_node:
        print("AI Agent node not found.")
        return

    # 5. Add node and connection
    wf["nodes"].append(memory_node)
    
    if "Postgres Chat Memory" not in wf["connections"]:
        wf["connections"]["Postgres Chat Memory"] = {
            "ai_memory": [
                [
                    {
                        "node": "AI Agent",
                        "type": "ai_memory",
                        "index": 0
                    }
                ]
            ]
        }
    
    # 6. Send update
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
        print("Success! Memory added to workflow.")
    else:
        print(f"Error updating: {put_resp.status_code} - {put_resp.text}")

if __name__ == "__main__":
    add_memory()
