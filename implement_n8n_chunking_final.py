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

def apply_final_patch():
    print(f"Fetching workflow {WORKFLOW_ID}...")
    response = requests.get(f"{BASE_URL}/workflows/{WORKFLOW_ID}", headers=headers)
    if response.status_code != 200:
        print(f"Failed to fetch: {response.text}")
        return
    
    wf = response.json()
    
    # 1. Limpiar nodos de metadatos de n8n (opcional, pero ayuda)
    # Algunos nodos pueden tener propiedades extrañas
    
    # 2. Agregar nuevos nodos
    loader_id = str(uuid.uuid4())
    splitter_id = str(uuid.uuid4())
    
    loader_node = {
        "parameters": {},
        "id": loader_id,
        "name": "Default Data Loader",
        "type": "@n8n/n8n-nodes-langchain.documentDefaultDataLoader",
        "typeVersion": 1,
        "position": [0, -350]
    }
    
    splitter_node = {
        "parameters": {
            "chunkSize": 4000,
            "chunkOverlap": 400
        },
        "id": splitter_id,
        "name": "Recursive Character Text Splitter",
        "type": "@n8n/n8n-nodes-langchain.textSplitterRecursiveCharacter",
        "typeVersion": 1,
        "position": [0, -500]
    }
    
    wf["nodes"].append(loader_node)
    wf["nodes"].append(splitter_node)
    
    # 3. Conexiones
    connections = wf["connections"]
    if "Download a file" in connections:
        connections["Download a file"]["main"][0].append({
            "node": "AI Agent",
            "type": "main",
            "index": 0
        })
        connections["Download a file"]["main"][0].append({
            "node": "Default Data Loader",
            "type": "main",
            "index": 0
        })
    
    connections["Default Data Loader"] = {
        "ai_document": [[{
            "node": "AI Agent",
            "type": "ai_document",
            "index": 0
        }]]
    }
    
    connections["Recursive Character Text Splitter"] = {
        "ai_textSplitter": [[{
            "node": "Default Data Loader",
            "type": "ai_textSplitter",
            "index": 0
        }]]
    }
    
    # 4. WHITELIST AGRESIVA
    # name, nodes, connections, settings son core.
    # staticData, meta, tags suelen ser aceptados.
    allowed_props = ["name", "nodes", "connections", "settings", "staticData", "meta", "tags"]
    update_payload = { k: wf[k] for k in allowed_props if k in wf }
    
    # Adicionalmente, n8n suele requerir que el ID NO esté en el payload si es un PUT a ese ID específico
    # aunque a veces lo acepta. Lo quitamos por si acaso.
    
    print("Sending final update with whitelist...")
    update_response = requests.put(f"{BASE_URL}/workflows/{WORKFLOW_ID}", headers=headers, json=update_payload)
    
    if update_response.status_code == 200:
        print("SUCCESS! Workflow updated with chunking.")
    else:
        print(f"Error: {update_response.status_code} - {update_response.text}")

if __name__ == "__main__":
    apply_final_patch()
