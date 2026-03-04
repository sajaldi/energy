import requests
import json

API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwOTM0MjU4Ni1jN2MzLTQ2ZjEtYmE1Mi00MjE3OTBkYWU0ZmQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiZTNjYjgzMzAtMDI2NS00NDRlLTkzNDItODk1NTM4YTEzZjAxIiwiaWF0IjoxNzcyNjM0NTYxfQ.r__JBW2L7qhAz7SAtqLw7XkS4pzn_28iDTLxFgkhXWc"
BASE_URL = "http://localhost:5678/api/v1"
WORKFLOW_ID = "vG1cO0fL8k520f1"

headers = {
    "X-N8N-API-KEY": API_KEY,
    "Accept": "application/json"
}

def get_workflow_details(workflow_id):
    try:
        response = requests.get(f"{BASE_URL}/workflows/{workflow_id}", headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Error fetching workflow details: {e}")
        return None

if __name__ == "__main__":
    details = get_workflow_details(WORKFLOW_ID)
    if details:
        with open("workflow_details.json", "w", encoding="utf-8") as f:
            json.dump(details, f, indent=2)
        print(f"Workflow {WORKFLOW_ID} details saved to workflow_details.json")
