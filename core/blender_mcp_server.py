import asyncio
import requests
import json
from mcp.server.fastmcp import FastMCP

# Configuración
BLENDER_BRIDGE_URL = "http://localhost:8012"

# Inicializar FastMCP
mcp = FastMCP("BlenderBridge")

@mcp.tool()
def get_blender_scene_info():
    """
    Obtiene información detallada de la escena actual en Blender (objetos, posiciones, nombres).
    """
    try:
        response = requests.post(BLENDER_BRIDGE_URL, json={"action": "get_scene"})
        return response.json()
    except Exception as e:
        return f"Error conectando con Blender: {str(e)}. ¿Está el Add-on activado y el Bridge iniciado?"

@mcp.tool()
def execute_blender_script(python_code: str):
    """
    Ejecuta código Python (bpy) dentro de Blender.
    Ejemplo: bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
    """
    try:
        response = requests.post(BLENDER_BRIDGE_URL, json={
            "action": "execute",
            "code": python_code
        })
        return response.json()
    except Exception as e:
        return f"Error ejecutando script: {str(e)}"

@mcp.tool()
def get_blender_screenshot():
    """
    Captura una imagen del viewport actual de Blender y devuelve la ruta del archivo.
    """
    try:
        response = requests.post(BLENDER_BRIDGE_URL, json={"action": "screenshot"})
        data = response.json()
        if data.get('status') == 'success':
            return f"Captura guardada en: {data.get('path')}"
        return data
    except Exception as e:
        return f"Error capturando pantalla: {str(e)}"

if __name__ == "__main__":
    mcp.run()
