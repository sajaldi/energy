"""
Tareas Celery para procesamiento asíncrono de consultas.
Genera embeddings usando Ollama local (sin rate limits).
Fallback a Gemini REST API si Ollama no está disponible.
"""
import logging
import time
import requests
from celery import shared_task

logger = logging.getLogger(__name__)

# Índice global para rotación de keys Gemini (fallback)
_current_key_index = 0

OLLAMA_URL = "http://localhost:11434"
OLLAMA_EMBED_MODEL = "nomic-embed-text"


def _get_gemini_keys():
    """
    Obtiene las API keys de Google (Gemini) desde la tabla GroqApiKey.
    Filtra por proveedor='google' y is_active=True, ordenadas por 'orden'.
    """
    try:
        from documentos.models import GroqApiKey
        keys = list(
            GroqApiKey.objects.filter(
                proveedor='google',
                is_active=True
            ).order_by('orden', 'created_at').values_list('api_key', flat=True)
        )
        return [k.strip() for k in keys if k.strip()]
    except Exception as e:
        logger.warning(f"Error obteniendo keys de GroqApiKey: {e}")
        from django.conf import settings
        single_key = getattr(settings, 'GEMINI_API_KEY', '')
        return [single_key] if single_key else []


def _ollama_disponible():
    """Verifica si Ollama está corriendo."""
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def _generar_embeddings_batch(textos, batch_size=50):
    """
    Genera embeddings. Intenta Ollama local primero (rápido, sin limits).
    Si Ollama no está disponible, usa Gemini REST API con rotación de keys.
    """
    # Intentar Ollama primero
    if _ollama_disponible():
        return _embeddings_ollama(textos)

    # Fallback: Gemini REST API
    return _embeddings_gemini(textos, batch_size)


def _embeddings_ollama(textos):
    """
    Genera embeddings con Ollama local.
    El endpoint /api/embed acepta múltiples textos de una vez.
    Sin rate limits, velocidad limitada solo por GPU/CPU.
    """
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/embed",
            json={
                "model": OLLAMA_EMBED_MODEL,
                "input": textos
            },
            timeout=120
        )

        if response.status_code == 200:
            data = response.json()
            return data['embeddings']
        else:
            logger.error(f"Error Ollama embed ({response.status_code}): {response.text[:200]}")
            return None
    except Exception as e:
        logger.error(f"Error Ollama embeddings: {e}")
        return None


def _embeddings_gemini(textos, batch_size=50):
    """Fallback: Gemini REST API con rotación de keys."""
    global _current_key_index

    keys = _get_gemini_keys()
    if not keys:
        logger.error("No hay API keys de Google activas y Ollama no disponible.")
        return None

    embeddings = []

    for i in range(0, len(textos), batch_size):
        batch = textos[i:i + batch_size]
        batch_done = False
        intentos = 0
        max_intentos = len(keys) * 3

        while not batch_done and intentos < max_intentos:
            key = keys[_current_key_index % len(keys)]
            batch_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents?key={key}"

            try:
                payload = {
                    "requests": [
                        {
                            "model": "models/gemini-embedding-001",
                            "content": {"parts": [{"text": t}]},
                            "outputDimensionality": 768,
                            "taskType": "RETRIEVAL_DOCUMENT"
                        }
                        for t in batch
                    ]
                }

                response = requests.post(batch_url, json=payload, timeout=60)

                if response.status_code == 200:
                    data = response.json()
                    for emb_obj in data.get('embeddings', []):
                        embeddings.append(emb_obj['values'])
                    batch_done = True
                    _current_key_index += 1
                    time.sleep(1.5)

                elif response.status_code == 429:
                    _current_key_index += 1
                    intentos += 1
                    if intentos % len(keys) == 0:
                        time.sleep(60)
                else:
                    logger.error(f"Error Gemini ({response.status_code}): {response.text[:200]}")
                    return None

            except Exception as e:
                logger.error(f"Error Gemini batch: {e}")
                return None

        if not batch_done:
            return None

    return embeddings


@shared_task(bind=True, max_retries=3)
def generar_embeddings_consulta(self, consulta_id):
    """Genera embeddings para todos los mensajes de una consulta."""
    from .models import Consulta, MensajeConsulta

    try:
        consulta = Consulta.objects.get(id=consulta_id)
        mensajes = list(
            consulta.mensajes.filter(embedding__isnull=True).exclude(
                texto='<Multimedia omitido>'
            )
        )

        total = len(mensajes)
        if total == 0:
            return {'current': 0, 'total': 0, 'percent': 100}

        self.update_state(state='PROGRESS', meta={
            'current': 0, 'total': total, 'percent': 0,
            'status': f'Iniciando... {total} mensajes pendientes'
        })

        batch_size = 50  # Ollama soporta batches grandes sin problema
        procesados = 0

        for i in range(0, total, batch_size):
            batch_mensajes = mensajes[i:i + batch_size]
            textos = [f"{m.remitente}: {m.texto}" for m in batch_mensajes]

            embeddings = _generar_embeddings_batch(textos, batch_size=len(textos))

            if embeddings:
                for msg, emb in zip(batch_mensajes, embeddings):
                    msg.embedding = emb
                MensajeConsulta.objects.bulk_update(batch_mensajes, ['embedding'], batch_size=100)
                procesados += len(batch_mensajes)
            else:
                procesados += len(batch_mensajes)

            percent = int((procesados / total) * 100)
            self.update_state(state='PROGRESS', meta={
                'current': procesados, 'total': total, 'percent': percent,
                'status': f'Procesados {procesados}/{total} ({percent}%)'
            })

        return {'current': procesados, 'total': total, 'percent': 100,
                'status': f'✅ Completado: {procesados}/{total} embeddings.'}

    except Consulta.DoesNotExist:
        logger.error(f"Consulta {consulta_id} no encontrada.")
    except Exception as exc:
        logger.exception(f"Error generando embeddings para consulta {consulta_id}")
        raise self.retry(exc=exc, countdown=60)
