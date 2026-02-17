import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

def notify_n8n_document_created(documento):
    """
    Envía una notificación a n8n cuando se crea un nuevo documento.
    """
    webhook_url = settings.N8N_WEBHOOK_URL
    if not webhook_url:
        logger.info("N8N_WEBHOOK_URL no configurado. Saltando notificación.")
        return False

    try:
        # Preparar datos del documento
        data = {
            'event': 'document_created',
            'id': documento.id,
            'codigo': documento.codigo,
            'titulo': documento.titulo,
            'tipo': documento.tipo_documento.nombre,
            'estado': documento.estado_actual,
            'fecha_creacion': documento.creado_en.isoformat(),
            'url_admin': f"{settings.SITE_URL}/admin/documentos/documento/{documento.id}/change/",
        }

        response = requests.post(webhook_url, json=data, timeout=5)
        response.raise_for_status()
        
        logger.info(f"Notificación enviada a n8n para el documento {documento.codigo}")
        return True
    except Exception as e:
        logger.error(f"Error al enviar notificación a n8n: {e}")
        return False
