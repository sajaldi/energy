import requests
import json

API_KEY = "AIzaSyD6NlcfSsDPTxNzefz6M8z_mEpEsJVaGkE"
MODEL = "gemini-3-flash-preview"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"

payload = {
    "contents": [{
        "parts": [{"text": "Hola, responde con un saludo corto."}]
    }]
}

try:
    response = requests.post(URL, json=payload, timeout=30)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
