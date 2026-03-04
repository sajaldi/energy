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

def execute_final_combined_patch():
    print(f"Fetching {WORKFLOW_ID}...")
    response = requests.get(f"{BASE_URL}/workflows/{WORKFLOW_ID}", headers=headers)
    wf = response.json()
    
    # IDs deterministicos para evitar duplicados si se re-ejecuta
    loader_id = "chunking-loader-001"
    splitter_id = "chunking-splitter-001"
    
    # Limpiar cualquier residuo de intentos previos con estos IDs
    wf["nodes"] = [n for n in wf["nodes"] if n.get("id") not in [loader_id, splitter_id]]

    # Agregar nodos con nombres VALIDADOS
    wf["nodes"].append({
        "parameters": {},
        "id": loader_id,
        "name": "Default Data Loader",
        "type": "@n8n/n8n-nodes-langchain.documentDefaultDataLoader",
        "typeVersion": 1,
        "position": [0, -250]
    })
    
    wf["nodes"].append({
        "parameters": {
            "chunkSize": 2000,
            "chunkOverlap": 200
        },
        "id": splitter_id,
        "name": "Recursive Character Text Splitter",
        "type": "@n8n/n8n-nodes-langchain.textSplitterRecursiveCharacterTextSplitter",
        "typeVersion": 1,
        "position": [0, -400]
    })
    
    # Actualizar conexiones
    conn = wf["connections"]
    
    # 1. Download a file -> AI Agent (Main) Y Loader (Main)
    # n8n binary data can be shared
    conn["Download a file"] = {
        "main": [[
            { "node": "AI Agent", "type": "main", "index": 0 },
            { "node": "Default Data Loader", "type": "main", "index": 0 }
        ]]
    }
    
    # 2. Loader -> AI Agent (ai_document)
    conn["Default Data Loader"] = {
        "ai_document": [[{ "node": "AI Agent", "type": "ai_document", "index": 0 }]]
    }
    
    # 3. Splitter -> Loader (ai_textSplitter)
    conn["Recursive Character Text Splitter"] = {
        "ai_textSplitter": [[{ "node": "Default Data Loader", "type": "ai_textSplitter", "index": 0 }]]
    }

    # PAYLOAD FINAL (Minimo + settings vacios)
    payload = {
        "name": wf["name"],
        "nodes": wf["nodes"],
        "connections": wf["connections"],
        "settings": {} # LA CLAVE DEL EXITO
    }
    
    print("Sending final combined update...")
    update_response = requests.put(f"{BASE_URL}/workflows/{WORKFLOW_ID}", headers=headers, json=payload)
    
    if update_response.status_code == 200:
        print("VICTORY! n8n workflow updated successfully with chunking.")
    else:
        print(f"CRITICAL FAILURE: {update_response.status_code}")
        print(f"Details: {update_response.text}")

if __name__ == "__main__":
    execute_final_combined_patch()
