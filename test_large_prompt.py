import requests
import json
import os

API_KEY = "AIzaSyD6NlcfSsDPTxNzefz6M8z_mEpEsJVaGkE"
MODEL = "gemini-3-flash-preview"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"

KNOWLEDGE_BASE_PATH = r"d:\Apps\energia\energy\core\ai_knowledge\knowledge.txt"

def get_knowledge_base():
    try:
        with open(KNOWLEDGE_BASE_PATH, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return ""

kb = get_knowledge_base()
prompt = f"Base de conocimientos:\n{kb[:500000]}\n\nPregunta: ¿Qué describe el KPI IE-01?"

payload = {
    "contents": [{
        "parts": [{"text": prompt}]
    }]
}

try:
    print(f"Sending prompt with length: {len(prompt)}")
    response = requests.post(URL, json=payload, timeout=60)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        if 'candidates' in data:
            print(f"Success! Response: {data['candidates'][0]['content']['parts'][0]['text'][:200]}...")
        else:
            print(f"No candidates! Response: {data}")
    else:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"Exception: {e}")
