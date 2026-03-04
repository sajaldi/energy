import requests
import json

API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwOTM0MjU4Ni1jN2MzLTQ2ZjEtYmE1Mi00MjE3OTBkYWU0ZmQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiZTNjYjgzMzAtMDI2NS00NDRlLTkzNDItODk1NTM4YTEzZjAxIiwiaWF0IjoxNzcyNjM0NTYxfQ.r__JBW2L7qhAz7SAtqLw7XkS4pzn_28iDTLxFgkhXWc"
BASE_URL = "http://localhost:5678/api/v1"

headers = {
    "X-N8N-API-KEY": API_KEY,
    "Accept": "application/json"
}

def list_node_types():
    try:
        # Note: Public API v1 might not have /node-types. 
        # But we can try /node-types or searching through existing workflows nodes.
        response = requests.get(f"{BASE_URL}/node-types", headers=headers)
        if response.status_code == 200:
            types = response.json()
            # Filter for langchain
            lc_types = [t for t in types if "langchain" in t.get("name", "").lower()]
            print(json.dumps(lc_types, indent=2))
        else:
            print(f"Error listing node types: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_node_types()
