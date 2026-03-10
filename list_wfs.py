import requests
import json

API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwOTM0MjU4Ni1jN2MzLTQ2ZjEtYmE1Mi00MjE3OTBkYWU0ZmQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiZTNjYjgzMzAtMDI2NS00NDRlLTkzNDItODk1NTM4YTEzZjAxIiwiaWF0IjoxNzcyNjM0NTYxfQ.r__JBW2L7qhAz7SAtqLw7XkS4pzn_28iDTLxFgkhXWc"
BASE_URL = "http://localhost:5678/api/v1"

headers = {
    "X-N8N-API-KEY": API_KEY,
    "Accept": "application/json"
}

def list_workflows():
    try:
        response = requests.get(f"{BASE_URL}/workflows", headers=headers, timeout=5)
        if response.status_code == 200:
            wfs = response.json().get('data', [])
            for wf in wfs:
                print(f"ID: {wf['id']} - Name: {wf['name']}")
        else:
            print(f"Error listing workflows: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Failed to connect to n8n: {e}")

if __name__ == "__main__":
    list_workflows()
