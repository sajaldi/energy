import os
import requests
import json
from django.conf import settings
from .ai_data_utils import get_dynamic_context

# Intentar obtener la API Key de settings o variables de entorno
API_KEY = getattr(settings, "GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))

# Actualizar modelos a versiones estables y existentes
MODEL = "gemini-1.5-flash" 
MODEL_REQUESTED = "gemini-1.5-flash"
FALLBACK_MODEL = "gemini-1.5-flash"

KNOWLEDGE_BASE_PATH = os.path.join(os.path.dirname(__file__), 'ai_knowledge', 'knowledge.txt')

def get_knowledge_base():
    try:
        if os.path.exists(KNOWLEDGE_BASE_PATH):
            with open(KNOWLEDGE_BASE_PATH, 'r', encoding='utf-8') as f:
                return f.read()
        return ""
    except Exception as e:
        print(f"Error reading knowledge base: {e}")
        return ""

def get_embedding(text, task_type="retrieval_document"):
    """Obtiene embedding usando Gemini u Ollama según configuración."""
    if API_KEY:
        import google.generativeai as genai
        genai.configure(api_key=API_KEY)
        try:
            result = genai.embed_content(
                model="models/text-embedding-004",
                content=text,
                task_type=task_type,
                output_dimensionality=384
            )
            return result['embedding']
        except Exception as e:
            print(f"Error Gemini embedding: {e}")
    
    # Fallback/Default a Ollama
    ollama_url = getattr(settings, "OLLAMA_URL", "http://localhost:11434")
    model = getattr(settings, "OLLAMA_MODEL_EMBEDDING", "nomic-embed-text")
    try:
        resp = requests.post(f"{ollama_url}/api/embeddings", json={
            "model": model,
            "prompt": text
        }, timeout=30)
        resp.raise_for_status()
        embedding = resp.json().get("embedding")
        return embedding[:384] if embedding else None
    except Exception as e:
        print(f"Error Ollama embedding: {e}")
        return None

def ask_ia(question, context="", system_prompt=None):
    """Interfaz unificada para preguntar a la IA (Gemini u Ollama)."""
    if not system_prompt:
        system_prompt = "Eres un asistente experto en el sistema CMMS."
    
    prompt = f"{system_prompt}\n\nContexto:\n{context}\n\nPregunta: {question}"

    if API_KEY:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_REQUESTED}:generateContent?key={API_KEY}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        try:
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            if 'candidates' in data and data['candidates']:
                return data['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            print(f"Error Gemini Chat: {e}")

    # Fallback/Default a Ollama
    ollama_url = getattr(settings, "OLLAMA_URL", "http://localhost:11434")
    model = getattr(settings, "OLLAMA_MODEL_CHAT", "llama3")
    try:
        resp = requests.post(f"{ollama_url}/api/generate", json={
            "model": model,
            "prompt": prompt,
            "stream": False
        }, timeout=90)
        resp.raise_for_status()
        return resp.json().get("response")
    except Exception as e:
        return f"Error en IA (Gemini/Ollama): {str(e)}"

def ask_gemini(question, context_limit=50000):
    """Mantenido por compatibilidad con código existente."""
    knowledge = get_knowledge_base()
    db_context = get_dynamic_context()
    context = f"Estado DB:\n{db_context}\n\nConocimiento:\n{knowledge[:context_limit]}"
    return ask_ia(question, context=context)
