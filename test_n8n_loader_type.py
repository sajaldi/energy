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

def test_loader_type():
    possible_loaders = [
        "@n8n/n8n-nodes-langchain.documentDefaultDataLoader",
        "n8n-nodes-langchain.documentDefaultDataLoader",
        "@n8n/n8n-nodes-langchain.documentLoaderDefault",
        "n8n-nodes-langchain.documentLoaderDefault"
    ]
    
    for ltype in possible_loaders:
        print(f"Testing loader type: {ltype}")
        test_wf = {
            "name": f"Test Loader Type {ltype[:10]}",
            "nodes": [
                {
                    "parameters": {},
                    "id": str(uuid.uuid4()),
                    "name": "Test Loader",
                    "type": ltype,
                    "typeVersion": 1,
                    "position": [0,0]
                }
            ],
            "connections": {},
            "settings": {}
        }
        
        response = requests.post(f"{BASE_URL}/workflows", headers=headers, json=test_wf)
        if response.status_code == 200:
            print(f"SUCCESS! Loader type '{ltype}' is valid.")
            # Cleanup
            new_id = response.json().get("id")
            requests.delete(f"{BASE_URL}/workflows/{new_id}", headers=headers)
            return ltype
        else:
            print(f"Failed: {response.text}")
            
    return None

if __name__ == "__main__":
    valid_type = test_loader_type()
    if valid_type:
        print(f"Valid type found: {valid_type}")
    else:
        print("No valid type found among candidates.")
