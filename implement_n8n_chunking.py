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

def apply_chunking():
    # 1. Fetch current workflow
    print(f"Fetching workflow {WORKFLOW_ID}...")
    response = requests.get(f"{BASE_URL}/workflows/{WORKFLOW_ID}", headers=headers)
    if response.status_code != 200:
        print(f"Failed to fetch workflow: {response.status_code} - {response.text}")
        return
    
    wf = response.json()
    
    # 2. Add new nodes
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
    
    # 3. Update connections
    # Current: Download a file -> AI Agent
    # New: Download a file -> Loader
    # Loader -> AI Agent (via ai_document)
    # Splitter -> Loader (via ai_textSplitter)
    
    connections = wf["connections"]
    
    # Connect Download a file (Binary) to Loader (Binary Input)
    if "Download a file" in connections:
        connections["Download a file"]["main"] = [[{
            "node": "Default Data Loader",
            "type": "main",
            "index": 0
        }]]
    
    # Connect Loader to AI Agent
    if "Default Data Loader" not in connections:
        connections["Default Data Loader"] = {}
    
    connections["Default Data Loader"]["ai_document"] = [[{
        "node": "AI Agent",
        "type": "ai_document",
        "index": 0
    }]]
    
    # Connect Splitter to Loader
    if "Recursive Character Text Splitter" not in connections:
        connections["Recursive Character Text Splitter"] = {}
        
    connections["Recursive Character Text Splitter"]["ai_textSplitter"] = [[{
        "node": "Default Data Loader",
        "type": "ai_textSplitter",
        "index": 0
    }]]
    
    # Ensure Aggregate also triggers the AI Agent (to start the chain)
    # The AI Agent needs a "Main" input trigger to start
    if "Aggregate" in connections:
        # We need to make sure the AI Agent still gets the 'Main' input from the flow
        # Current: Aggregate -> Download a file
        # Download a file -> Loader
        # Loader -> AI Agent ??? 
        # Wait, Loader doesn't have a 'main' output for the agent.
        # So we should connect Aggregate directly to AI Agent (main) too, but only once it's ready.
        # Actually, Download a file -> AI Agent was the original.
        # If we change Download a file to point to Loader, the AI Agent loses its 'Main' input.
        
        # Correct path:
        # Webhook -> ... -> Aggregate -> Download a file -> (main) -> AI Agent (main)
        # AND Loader (ai_document) -> AI Agent (ai_document)
        # AND Splitter (ai_textSplitter) -> Loader (ai_textSplitter)
        
        # Restore Download a file -> AI Agent (main)
        connections["Download a file"]["main"] = [[{
            "node": "AI Agent",
            "type": "main",
            "index": 0
        }]]
        
        # Add Download a file -> Loader (main)
        connections["Download a file"]["main"][0].append({
            "node": "Default Data Loader",
            "type": "main",
            "index": 0
        })

    # 4. Clean and update
    allowed_props = ["name", "nodes", "connections", "settings", "staticData", "meta", "tags", "active"]
    update_payload = { k: wf[k] for k in allowed_props if k in wf }
    
    print("Sending update payload...")
    update_response = requests.put(f"{BASE_URL}/workflows/{WORKFLOW_ID}", headers=headers, json=update_payload)
    
    if update_response.status_code == 200:
        print("Success! n8n workflow updated with chunking nodes.")
    else:
        print(f"Update failed: {update_response.status_code} - {update_response.text}")

if __name__ == "__main__":
    apply_chunking()
