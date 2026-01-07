import os
import requests
import json
from .ai_data_utils import get_dynamic_context

API_KEY = "AIzaSyD6NlcfSsDPTxNzefz6M8z_mEpEsJVaGkE"
MODEL = "gemini-1.5-flash" # Defaulting to 1.5-flash as it's stable, though user mentioned "gemini-3-flash-preview"
# NOTE: "gemini-3-flash-preview" is likely a future-looking request or typo for 2.0. 
# I will use a flexible approach or a robust model. 
# Actually, I'll try the exact string requested by the user first.
MODEL_REQUESTED = "gemini-3-flash-preview"
FALLBACK_MODEL = "gemini-flash-latest" # Verified as available in list_models

KNOWLEDGE_BASE_PATH = os.path.join(os.path.dirname(__file__), 'ai_knowledge', 'knowledge.txt')

def get_knowledge_base():
    try:
        with open(KNOWLEDGE_BASE_PATH, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading knowledge base: {e}")
        return ""

def ask_gemini(question, context_limit=50000):
    """
    Sends a question to Gemini using the knowledge base and DB status as context.
    """
    knowledge = get_knowledge_base()
    db_context = get_dynamic_context()
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_REQUESTED}:generateContent?key={API_KEY}"
    
    prompt = f"""
Eres un Asistente experto en el Contrato del Centro Cívico Gubernamental (CCG) y en el estado actual del sistema CMMS.
Tu base de conocimientos incluye el contrato adjunto y los datos actuales de la base de datos (proyectos, activos, documentos).

Responde de manera profesional, precisa y citando secciones si es posible.
Si la información no está en los documentos ni en la BD, indícalo educadamente.

---
{db_context}

---
CONTRATO / BASE DE CONOCIMIENTOS:
{knowledge[:400000]} # Slightly reduced to accommodate DB context

PREGUNTA DEL USUARIO:
{question}
"""

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }

    try:
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        if 'candidates' in data and data['candidates']:
            return data['candidates'][0]['content']['parts'][0]['text']
        else:
            print(f"API Response without candidates: {data}")
            return f"Error de API (sin candidatos): {json.dumps(data)}"
    except Exception as e:
        print(f"Error en ask_gemini: {str(e)}")
        # Fallback to a confirmed existing model if gemini-3 fails
        print(f"Requested model {MODEL_REQUESTED} failed, falling back to {FALLBACK_MODEL}.")
        return ask_gemini_fallback(question, knowledge)

def ask_gemini_fallback(question, knowledge):
    db_context = get_dynamic_context()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{FALLBACK_MODEL}:generateContent?key={API_KEY}"
    prompt = f"{db_context}\n\nBase de conocimientos:\n{knowledge[:150000]}\n\nPregunta: {question}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        if 'candidates' in data and data['candidates']:
            return data['candidates'][0]['content']['parts'][0]['text']
        return f"Error crítico en fallback: {json.dumps(data)}"
    except Exception as e:
        return f"Error crítico: {str(e)}"
