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

def final_surgical_cleanup():
    print(f"Fetching {WORKFLOW_ID}...")
    response = requests.get(f"{BASE_URL}/workflows/{WORKFLOW_ID}", headers=headers)
    wf = response.json()
    
    # 1. ELIMINACION RADICAL DE NODOS INVALIDOS
    # Solo permitimos los tipos base que sabemos que funcionan
    allowed_types = [
        "n8n-nodes-base.webhook",
        "n8n-nodes-base.s3",
        "n8n-nodes-base.postgres",
        "@n8n/n8n-nodes-langchain.agent",
        "n8n-nodes-base.aggregate",
        "@n8n/n8n-nodes-langchain.lmChatGroq",
        "n8n-nodes-base.code"
    ]
    
    print("Pre-cleanup nodes:")
    for n in wf["nodes"]:
        print(f"- {n.get('name')} (Type: {n.get('type')})")
        
    wf["nodes"] = [n for n in wf["nodes"] if n.get("type") in allowed_types]

    # 2. Agregar los dos nuevos nodos validados
    loader_id = str(uuid.uuid4())
    splitter_id = str(uuid.uuid4())
    
    wf["nodes"].append({
        "parameters": {},
        "id": loader_id,
        "name": "Default Data Loader",
        "type": "@n8n/n8n-nodes-langchain.documentDefaultDataLoader",
        "typeVersion": 1,
        "position": [0, -300]
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
    
    # 3. Conexiones (Asegurar que existan los nodos involucrados)
    conn = wf["connections"]
    # Limpiar conexiones de nodos que ya no existen
    # (n8n no suele fallar por esto pero es mejor ser limpio)
    
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

    # 4. Payload ultra-limpio
    payload = {
        "name": wf["name"],
        "nodes": wf["nodes"],
        "connections": wf["connections"],
        "settings": {}
    }
    
    print("Post-cleanup nodes:")
    for n in payload["nodes"]:
        print(f"- {n.get('name')} (Type: {n.get('type')})")

    print("Sending final CLEAN update...")
    update_response = requests.put(f"{BASE_URL}/workflows/{WORKFLOW_ID}", headers=headers, json=payload)
    
    if update_response.status_code == 200:
        print("ULTIMATE VICTORY! Workflow updated.")
    else:
        print(f"FAILURE AGAIN: {update_response.status_code} - {update_response.text}")

if __name__ == "__main__":
    final_surgical_cleanup()
