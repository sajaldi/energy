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

def patch_workflow():
    try:
        with open("workflows_found.json", "r", encoding="utf-8") as f:
            all_workflows = json.load(f)
            wf = next((w for w in all_workflows if w["id"] == WORKFLOW_ID), None)
            if not wf:
                print("Workflow not found in JSON file.")
                return
    except Exception as e:
        print(f"Error reading local JSON: {e}")
        return

    # Definir nuevos IDs
    loader_id = str(uuid.uuid4())
    splitter_id = str(uuid.uuid4())
    
    loader_node = {
        "parameters": {
            "options": {}
        },
        "id": loader_id,
        "name": "Default Data Loader",
        "type": "@n8n/n8n-nodes-langchain.documentDefaultDataLoader",
        "typeVersion": 1,
        "position": [-40, -352]
    }
    
    splitter_node = {
        "parameters": {
            "chunkSize": 1000,
            "chunkOverlap": 100
        },
        "id": splitter_id,
        "name": "Recursive Character Text Splitter",
        "type": "@n8n/n8n-nodes-langchain.textSplitterRecursiveCharacter",
        "typeVersion": 1,
        "position": [-40, -500]
    }

    # Agregar nodos
    wf["nodes"].append(loader_node)
    wf["nodes"].append(splitter_node)

    # Actualizar conexiones
    connections = wf["connections"]
    
    # Download a file -> Default Data Loader
    if "Download a file" in connections:
        connections["Download a file"]["main"] = [[{
            "node": "Default Data Loader",
            "type": "main",
            "index": 0
        }]]
    
    # Loader e AI Agent slots
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
    
    if "Aggregate" in connections:
        connections["Aggregate"]["main"][0].append({
            "node": "AI Agent",
            "type": "main",
            "index": 0
        })

    # LIMPIEZA CRITICA: Solo enviar lo que n8n permite en el PUT
    # Según docs de n8n, el cuerpo debe ser { "name": "...", "nodes": [...], "connections": {...}, "settings": {...}, "staticData": ..., "meta": ..., "tags": [...] }
    # NO debe incluir id, createdAt, updatedAt, versionId, etc.
    
    allowed_props = ["name", "nodes", "connections", "settings", "staticData", "meta", "tags"]
    update_payload = { k: wf[k] for k in allowed_props if k in wf }
    
    # También limpiar IDs internos de nodos si es necesario, pero usualmente n8n los acepta si son UUIDs
    
    print("Sending cleaned update to n8n...")
    response = requests.put(f"{BASE_URL}/workflows/{WORKFLOW_ID}", headers=headers, json=update_payload)
    
    if response.status_code == 200:
        print("Workflow updated successfully!")
    else:
        print(f"Error updating workflow: {response.status_code} - {response.text}")

if __name__ == "__main__":
    patch_workflow()
