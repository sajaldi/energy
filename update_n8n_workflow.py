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
    # 1. Cargar el JSON actual
    try:
        with open("workflows_found.json", "r", encoding="utf-8") as f:
            all_workflows = json.load(f)
            # Buscar el que coincide con el ID
            wf = next((w for w in all_workflows if w["id"] == WORKFLOW_ID), None)
            if not wf:
                print("Workflow not found in JSON file.")
                return
    except Exception as e:
        print(f"Error reading local JSON: {e}")
        return

    # 2. Definir nuevos nodos
    loader_id = str(uuid.uuid4())
    splitter_id = str(uuid.uuid4())
    
    loader_node = {
        "parameters": {
            "options": {}
        },
        "type": "@n8n/n8n-nodes-langchain.documentDefaultDataLoader",
        "typeVersion": 1,
        "position": [
            -40,
            -352
        ],
        "id": loader_id,
        "name": "Default Data Loader"
    }
    
    splitter_node = {
        "parameters": {
            "chunkSize": 1000,
            "chunkOverlap": 100
        },
        "type": "@n8n/n8n-nodes-langchain.textSplitterRecursiveCharacter",
        "typeVersion": 1,
        "position": [
            -40,
            -500
        ],
        "id": splitter_id,
        "name": "Recursive Character Text Splitter"
    }

    # Agregar nodos
    wf["nodes"].append(loader_node)
    wf["nodes"].append(splitter_node)

    # 3. Actualizar conexiones
    # Reemplazar Download a file -> AI Agent con Download a file -> Loader
    # Download a file ID: bd600126-36d9-4e12-b995-24abd2fce5cc
    # AI Agent ID: f9a1d2ca-ebd5-4797-93a5-63f26d1b4ab1
    
    connections = wf["connections"]
    
    # Download a file -> Default Data Loader
    if "Download a file" in connections:
        connections["Download a file"]["main"] = [[{
            "node": "Default Data Loader",
            "type": "main",
            "index": 0
        }]]
    
    # Loader connections
    connections["Default Data Loader"] = {
        "ai_document": [[{
            "node": "AI Agent",
            "type": "ai_document",
            "index": 0
        }]]
    }
    
    # Splitter connections
    connections["Recursive Character Text Splitter"] = {
        "ai_textSplitter": [[{
            "node": "Default Data Loader",
            "type": "ai_textSplitter",
            "index": 0
        }]]
    }
    
    # Conectar Aggregate -> AI Agent (main) para disparar la ejecución
    # Aggregate ID: 2bc877d8-22c5-48cb-99f1-c7bdc66f80fb
    if "Aggregate" in connections:
        # Mantener la conexión a Download a file y agregar a AI Agent
        connections["Aggregate"]["main"][0].append({
            "node": "AI Agent",
            "type": "main",
            "index": 0
        })

    # 4. Enviar actualización
    # NOTA: n8n API espera el objeto workflow con 'nodes', 'connections', etc.
    update_payload = {
        "nodes": wf["nodes"],
        "connections": wf["connections"],
        "name": wf["name"],
        "active": wf.get("active", False),
        "settings": wf.get("settings", {}),
        "staticData": wf.get("staticData", None),
        "meta": wf.get("meta", {}),
        "tags": wf.get("tags", [])
    }
    
    print("Sending update to n8n...")
    response = requests.put(f"{BASE_URL}/workflows/{WORKFLOW_ID}", headers=headers, json=update_payload)
    
    if response.status_code == 200:
        print("Workflow updated successfully!")
    else:
        print(f"Error updating workflow: {response.status_code} - {response.text}")

if __name__ == "__main__":
    patch_workflow()
