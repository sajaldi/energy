import requests
import json
import uuid

API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwOTM0MjU4Ni1jN2MzLTQ2ZjEtYmE1Mi00MjE3OTBkYWU0ZmQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiZTNjYjgzMzAtMDI2NS00NDRlLTkzNDItODk1NTM4YTEzZjAxIiwiaWF0IjoxNzcyNjM0NTYxfQ.r__JBW2L7qhAz7SAtqLw7XkS4pzn_28iDTLxFgkhXWc"
BASE_URL = "http://localhost:5678/api/v1"
WORKFLOW_ID = "nAK6DyfCZkZXlBKo"

headers = {
    "X-N8N-API-KEY": API_KEY,
    "Accept": "application/json",
    "Content-Type": "application/json"
}

def apply_surgical_patch():
    print(f"Surgical fetch for {WORKFLOW_ID}...")
    response = requests.get(f"{BASE_URL}/workflows/{WORKFLOW_ID}", headers=headers)
    if response.status_code != 200:
        print(f"Fetch failed: {response.text}")
        return
    
    wf = response.json()
    print(f"Current root keys: {list(wf.keys())}")
    
    # 1. Add nodes
    loader_id = str(uuid.uuid4())
    splitter_id = str(uuid.uuid4())
    
    wf["nodes"].append({
        "parameters": {},
        "id": loader_id,
        "name": "Default Data Loader",
        "type": "@n8n/n8n-nodes-langchain.documentDefaultDataLoader",
        "typeVersion": 1,
        "position": [0, -350]
    })
    
    wf["nodes"].append({
        "parameters": {
            "chunkSize": 4000,
            "chunkOverlap": 400
        },
        "id": splitter_id,
        "name": "Recursive Character Text Splitter",
        "type": "@n8n/n8n-nodes-langchain.textSplitterRecursiveCharacter",
        "typeVersion": 1,
        "position": [0, -500]
    })
    
    # 2. Update connections
    conn = wf["connections"]
    if "Download a file" in conn:
        # Original: Download a file -> AI Agent
        # New: Download a file -> AI Agent AND Loader
        conn["Download a file"]["main"][0].append({
            "node": "Default Data Loader",
            "type": "main",
            "index": 0
        })
    
    conn["Default Data Loader"] = {
        "ai_document": [[{
            "node": "AI Agent",
            "type": "ai_document",
            "index": 0
        }]]
    }
    
    conn["Recursive Character Text Splitter"] = {
        "ai_textSplitter": [[{
            "node": "Default Data Loader",
            "type": "ai_textSplitter",
            "index": 0
        }]]
    }

    # 3. Aggressive Cleansing
    # Clean Root
    root_whitelist = ["name", "nodes", "connections", "settings", "staticData", "meta", "tags", "active"]
    payload = { k: wf[k] for k in root_whitelist if k in wf }
    
    # Clean Settings (Remove problematic ones)
    if "settings" in payload:
        # According to research, these can cause 400 Errors in PUT
        problematic_settings = ["callerPolicy", "executionOrder", "timeSavedMode", "timeSavedValue", "timeSavedUnit"]
        for p in problematic_settings:
            if p in payload["settings"]:
                print(f"Removing setting: {p}")
                del payload["settings"][p]
    
    # Clean Nodes
    # n8n generates its own internal data for nodes, we should only send the essentials
    node_whitelist = ["id", "name", "type", "typeVersion", "position", "parameters", "webhookId", "credentials", "disabled", "notes", "notesInFlow"]
    new_nodes = []
    for node in payload["nodes"]:
        cleaned_node = { k: node[k] for k in node_whitelist if k in node }
        new_nodes.append(cleaned_node)
    payload["nodes"] = new_nodes

    print("Sending surgical update...")
    update_response = requests.put(f"{BASE_URL}/workflows/{WORKFLOW_ID}", headers=headers, json=payload)
    
    if update_response.status_code == 200:
        print("PERFECT! Workflow updated.")
    else:
        print(f"STILL FAILED: {update_response.status_code}")
        print(f"Error Details: {update_response.text}")

if __name__ == "__main__":
    apply_surgical_patch()
