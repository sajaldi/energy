import requests
import json
import uuid

API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwOTM0MjU4Ni1jN2MzLTQ2ZjEtYmE1Mi00MjE3OTBkYWU0ZmQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiZTNjYjgzMzAtMDI2NS00NDRlLTkzNDItODk1NTM4YTEzZjAxIiwiaWF0IjoxNzcyNjM0NTYxfQ.r__JBW2L7qhAz7SAtqLw7XkS4pzn_28iDTLxFgkhXWc"
BASE_URL = "http://localhost:5678/api/v1"

headers = {
    "X-N8N-API-KEY": API_KEY,
    "Accept": "application/json",
    "Content-Type": "application/json"
}

def test_node_types():
    # Posibles nombres para el Splitter
    possible_splitters = [
        "@n8n/n8n-nodes-langchain.textSplitterRecursiveCharacterTextSplitter",
        "@n8n/n8n-nodes-langchain.textSplitterRecursiveCharacter",
        "n8n-nodes-langchain.textSplitterRecursiveCharacterTextSplitter",
        "n8n-nodes-langchain.textSplitterRecursiveCharacter"
    ]
    
    for stype in possible_splitters:
        print(f"Testing node type: {stype}")
        test_wf = {
            "name": f"Test Node Type {stype[:10]}",
            "nodes": [
                {
                    "parameters": {},
                    "id": str(uuid.uuid4()),
                    "name": "Test Splitter",
                    "type": stype,
                    "typeVersion": 1,
                    "position": [0,0]
                }
            ],
            "connections": {},
            "settings": {}
        }
        
        response = requests.post(f"{BASE_URL}/workflows", headers=headers, json=test_wf)
        if response.status_code == 200:
            print(f"SUCCESS! Node type '{stype}' is valid.")
            # Cleanup
            new_id = response.json().get("id")
            requests.delete(f"{BASE_URL}/workflows/{new_id}", headers=headers)
            return stype
        else:
            print(f"Failed: {response.text}")
            
    return None

if __name__ == "__main__":
    valid_type = test_node_types()
    if valid_type:
        print(f"Valid type found: {valid_type}")
    else:
        print("No valid type found among candidates.")
