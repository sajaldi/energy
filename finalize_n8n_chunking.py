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

def finalize_patch():
    print(f"Fetching workflow {WORKFLOW_ID}...")
    response = requests.get(f"{BASE_URL}/workflows/{WORKFLOW_ID}", headers=headers)
    if response.status_code != 200:
        print(f"Fetch failed: {response.text}")
        return
    
    wf = response.json()
    
    # 1. REMOVE GHOST NODES (from previous failed attempts)
    # Filter out any nodes that might have been partially added but are unrecognized
    valid_original_node_ids = ["fa2f0695-f9de-4c9c-b83a-b84145db865c", "bd600126-36d9-4e12-b995-24abd2fce5cc", 
                              "82a630bb-e2d9-4c83-9ce0-8f6c116a18b7", "f9a1d2ca-ebd5-4797-93a5-63f26d1b4ab1",
                              "2bc877d8-22c5-48cb-99f1-c7bdc66f80fb", "c585b2c5-28d5-433d-88a2-1eb4a4831be5",
                              "5e3c7f66-d19a-4113-9481-ad410bc7a31e", "a1d776fe-7e58-4cde-baab-e9dd98c520f1"]
    
    wf["nodes"] = [n for n in wf["nodes"] if n.get("id") in valid_original_node_ids]

    # 2. Add VALID nodes
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
        "type": "@n8n/n8n-nodes-langchain.textSplitterRecursiveCharacterTextSplitter",
        "typeVersion": 1,
        "position": [0, -500]
    })
    
    # 3. Update connections
    conn = wf["connections"]
    
    # Reset Download a file connections to be safe
    # Node name is "Download a file"
    conn["Download a file"] = {
        "main": [[
            { "node": "AI Agent", "type": "main", "index": 0 },
            { "node": "Default Data Loader", "type": "main", "index": 0 }
        ]]
    }
    
    conn["Default Data Loader"] = {
        "ai_document": [[{ "node": "AI Agent", "type": "ai_document", "index": 0 }]]
    }
    
    conn["Recursive Character Text Splitter"] = {
        "ai_textSplitter": [[{ "node": "Default Data Loader", "type": "ai_textSplitter", "index": 0 }]]
    }

    # 4. Cleansing again
    root_whitelist = ["name", "nodes", "connections", "settings", "staticData", "meta", "tags"]
    payload = { k: wf[k] for k in root_whitelist if k in wf }
    payload["settings"] = {} # Hard reset settings to avoid 400

    print("Sending final validated update...")
    update_response = requests.put(f"{BASE_URL}/workflows/{WORKFLOW_ID}", headers=headers, json=payload)
    
    if update_response.status_code == 200:
        print("BINGO! Workflow successfully updated and chunking implemented.")
    else:
        print(f"STILL FAILED: {update_response.status_code} - {update_response.text}")

if __name__ == "__main__":
    finalize_patch()
