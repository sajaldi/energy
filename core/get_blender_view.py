import requests
import json
import os

BLENDER_BRIDGE_URL = "http://localhost:8012"

try:
    # 1. Solicitar captura
    response = requests.post(BLENDER_BRIDGE_URL, json={"action": "screenshot"}, timeout=15)
    data = response.json()
    print(json.dumps(data))
    
    # 2. Si tuvo éxito, la ruta está en data['path']
except Exception as e:
    print(f"Error capturando pantalla: {e}")
