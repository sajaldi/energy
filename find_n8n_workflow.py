import requests
import json

API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwOTM0MjU4Ni1jN2MzLTQ2ZjEtYmE1Mi00MjE3OTBkYWU0ZmQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiZTNjYjgzMzAtMDI2NS00NDRlLTkzNDItODk1NTM4YTEzZjAxIiwiaWF0IjoxNzcyNjM0NTYxfQ.r__JBW2L7qhAz7SAtqLw7XkS4pzn_28iDTLxFgkhXWc"
BASE_URL = "http://localhost:5678/api/v1"

headers = {
    "X-N8N-API-KEY": API_KEY,
    "Accept": "application/json"
}

def find_workflow(name_query):
    try:
        response = requests.get(f"{BASE_URL}/workflows", headers=headers)
        if response.status_code == 200:
            data = response.json()
            workflows = data.get('data', [])
            matches = [w for w in workflows if name_query.lower() in w.get('name', '').lower()]
            return matches
        else:
            print(f"Error: {response.text}")
            return []
    except Exception as e:
        print(f"Error searching workflow: {e}")
        return []

if __name__ == "__main__":
    matches = find_workflow("OBTENER METADATA DE DOCUMENTOS")
    print(json.dumps(matches, indent=2))
