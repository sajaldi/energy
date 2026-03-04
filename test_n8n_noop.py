import requests
import json

API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwOTM0MjU4Ni1jN2MzLTQ2ZjEtYmE1Mi00MjE3OTBkYWU0ZmQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiZTNjYjgzMzAtMDI2NS00NDRlLTkzNDItODk1NTM4YTEzZjAxIiwiaWF0IjoxNzcyNjM0NTYxfQ.r__JBW2L7qhAz7SAtqLw7XkS4pzn_28iDTLxFgkhXWc"
BASE_URL = "http://localhost:5678/api/v1"
WORKFLOW_ID = "nAK6DyfCZkZXlBKo"

headers = {
    "X-N8N-API-KEY": API_KEY,
    "Accept": "application/json",
    "Content-Type": "application/json"
}

def test_noop_update():
    print(f"Fetching {WORKFLOW_ID}...")
    response = requests.get(f"{BASE_URL}/workflows/{WORKFLOW_ID}", headers=headers)
    wf = response.json()
    
    # Try the most minimal set possible
    payload = {
        "name": wf["name"],
        "nodes": wf["nodes"],
        "connections": wf["connections"],
        "settings": wf.get("settings", {})
    }
    
    # Surgical removal of known problematic root keys
    for k in ["id", "updatedAt", "createdAt", "versionId", "activeVersionId", "shared", "triggerCount", "isArchived", "staticData", "meta", "tags"]:
        if k in payload:
            del payload[k]
            
    # Surgical removal of known problematic settings
    for p in ["callerPolicy", "executionOrder", "timeSavedMode", "timeSavedValue", "timeSavedUnit", "availableInMCP"]:
        if p in payload["settings"]:
            del payload["settings"][p]

    print("Sending NO-OP update...")
    update_response = requests.put(f"{BASE_URL}/workflows/{WORKFLOW_ID}", headers=headers, json=payload)
    print(f"Status: {update_response.status_code}")
    print(f"Response: {update_response.text}")

if __name__ == "__main__":
    test_noop_update()
