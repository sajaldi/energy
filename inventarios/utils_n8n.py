import requests
import logging
import json
from django.conf import settings
from decimal import Decimal

logger = logging.getLogger(__name__)

def notify_n8n_solicitud_material(solicitud):
    """
    Envía una notificación a n8n cuando se crea una nueva solicitud de materiales.
    Incluye todos los datos de la solicitud y sus ítems.
    """
    webhook_url = getattr(settings, 'N8N_SOLICITUD_WEBHOOK_URL', None)
    if not webhook_url:
        logger.info("N8N_SOLICITUD_WEBHOOK_URL no configurado. Saltando notificación.")
        return False

    try:
        # Obtener los ítems asociados
        items = []
        for mov in solicitud.items.all():
            items.append({
                'material_id': mov.material.id,
                'material_nombre': mov.material.nombre,
                'sku': mov.material.sku,
                'cantidad': float(mov.cantidad),
                'unidad': mov.material.unidad_medida.nombre if mov.material.unidad_medida else "Unidad",
            })

        # Preparar datos de la solicitud
        data = {
            'event': 'solicitud_material_created',
            'solicitud_id': solicitud.id,
            'fecha': solicitud.fecha_solicitud.isoformat(),
            'usuario': solicitud.usuario.username,
            'usuario_nombre': f"{solicitud.usuario.first_name} {solicitud.usuario.last_name}".strip(),
            'ubicacion_origen': solicitud.ubicacion_origen.nombre,
            'orden_trabajo': solicitud.orden_trabajo.numero_ot if solicitud.orden_trabajo else "N/A",
            'ot_id': solicitud.orden_trabajo.id if solicitud.orden_trabajo else None,
            'comentarios': solicitud.comentarios_solicitud or "",
            'items': items,
            'url_admin': f"{settings.SITE_URL}/admin/inventarios/solicitudmaterial/{solicitud.id}/change/",
            'url_app': f"{settings.SITE_URL}/inventarios/mobile/pedidos/{solicitud.id}/",
        }

        # Enviar el webhook
        response = requests.post(webhook_url, json=data, timeout=5)
        response.raise_for_status()
        
        logger.info(f"Notificación enviada a n8n para la solicitud #{solicitud.id}")
        return True
    except Exception as e:
        logger.error(f"Error al enviar notificación a n8n por solicitud #{solicitud.id}: {e}")
        return False
