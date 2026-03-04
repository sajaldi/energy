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

def apply_brute_patch():
    response = requests.get(f"{BASE_URL}/workflows/{WORKFLOW_ID}", headers=headers)
    wf = response.json()
    
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
        "parameters": { "chunkSize": 4000, "chunkOverlap": 400 },
        "id": splitter_id,
        "name": "Recursive Character Text Splitter",
        "type": "@n8n/n8n-nodes-langchain.textSplitterRecursiveCharacter",
        "typeVersion": 1,
        "position": [0, -500]
    })
    
    conn = wf["connections"]
    if "Download a file" in conn:
        conn["Download a file"]["main"][0].append({ "node": "Default Data Loader", "type": "main", "index": 0 })
    conn["Default Data Loader"] = { "ai_document": [[{ "node": "AI Agent", "type": "ai_document", "index": 0 }]] }
    conn["Recursive Character Text Splitter"] = { "ai_textSplitter": [[{ "node": "Default Data Loader", "type": "ai_textSplitter", "index": 0 }]] }

    # BRUTE FORCE PAYLOAD
    payload = {
        "name": wf["name"],
        "nodes": wf["nodes"],
        "connections": wf["connections"],
        "settings": {} # COMPLETAMENTE VACIO
    }
    
    print("Sending brute update...")
    update_response = requests.put(f"{BASE_URL}/workflows/{WORKFLOW_ID}", headers=headers, json=payload)
    print(f"Status: {update_response.status_code}")
    print(f"Response: {update_response.text}")

if __name__ == "__main__":
    apply_brute_patch()
