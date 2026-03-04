import requests
import json

API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwOTM0MjU4Ni1jN2MzLTQ2ZjEtYmE1Mi00MjE3OTBkYWU0ZmQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiZTNjYjgzMzAtMDI2NS00NDRlLTkzNDItODk1NTM4YTEzZjAxIiwiaWF0IjoxNzcyNjM0NTYxfQ.r__JBW2L7qhAz7SAtqLw7XkS4pzn_28iDTLxFgkhXWc"
BASE_URL = "http://localhost:5678/api/v1"

headers = {
    "X-N8N-API-KEY": API_KEY,
    "Accept": "application/json"
}

def test_connection():
    try:
        # Listar flujos para probar la conexión
        response = requests.get(f"{BASE_URL}/workflows", headers=headers, params={"limit": 5})
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print("Successfully connected to n8n!")
            print(f"Found {len(data.get('data', []))} workflows (limited to 5 for test).")
            for wf in data.get('data', []):
                print(f"- {wf.get('name')} (ID: {wf.get('id')})")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Network error: {e}")

if __name__ == "__main__":
    test_connection()
