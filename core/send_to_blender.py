import requests
import json
import sys

# Leer el código del archivo de modelado (cambiar según el activo)
try:
    with open('d:/Apps/energia/energy/core/modeling_panel.py', 'r') as f:
        bpy_code = f.read()
except Exception as e:
    print(f"Error leyendo script: {e}")
    sys.exit(1)

# Enviar al Bridge
BLENDER_BRIDGE_URL = "http://localhost:8012"

try:
    response = requests.post(BLENDER_BRIDGE_URL, json={
        "action": "execute",
        "code": bpy_code
    }, timeout=10)
    print(response.json())
except Exception as e:
    print(f"Error conectando con Blender Bridge: {e}")
