import requests
import logging
from django.conf import settings
from django.forms.models import model_to_dict

logger = logging.getLogger(__name__)

def notify_requisicion_finalizada(requisicion):
    """
    Envía un webhook cuando una requisición es finalizada.
    Extrae la información de la requisición, el solicitante y su jefe directo.
    """
    url = getattr(settings, 'N8N_SOLICITUD_WEBHOOK_URL', None)
    if not url:
        logger.warning("N8N_SOLICITUD_WEBHOOK_URL no configurado en settings.py")
        return False

    # 1. Información de la Requisición
    req_data = model_to_dict(requisicion, exclude=['articulos', 'documentos', 'proveedores_sugeridos'])
    req_data['cr8ca_requisicionid'] = str(requisicion.cr8ca_requisicionid)
    req_data['total_estimado'] = float(requisicion.total_estimado)
    req_data['prioridad_display'] = requisicion.get_cr8ca_prioridad_display()
    req_data['estado_display'] = requisicion.get_estado_requisicion_display()
    
    # Artículos
    articulos = []
    for art in requisicion.articulos.all():
        art_dict = model_to_dict(art)
        art_dict['cr8ca_itemderequisicionid'] = str(art.cr8ca_itemderequisicionid)
        art_dict['material_nombre'] = art.material.nombre if art.material else ""
        art_dict['subtotal'] = float(art.subtotal)
        art_dict['cr8ca_cantidad'] = float(art.cr8ca_cantidad)
        art_dict['cr8ca_costoaproximado'] = float(art.cr8ca_costoaproximado) if art.cr8ca_costoaproximado else 0
        articulos.append(art_dict)
    
    # 2. Información del Solicitante
    solicitante = requisicion.usuario_solicitante
    solicitante_data = {}
    if solicitante:
        perfil = getattr(solicitante, 'perfil', None)
        solicitante_data = {
            'id': solicitante.id,
            'username': solicitante.username,
            'email': solicitante.email,
            'nombre_completo': f"{solicitante.first_name} {solicitante.last_name}".strip(),
            'telefono': perfil.telefono if perfil else None
        }

    # 3. Información del Responsable / Jefe Directo
    responsable_data = {}
    if solicitante and hasattr(solicitante, 'perfil') and solicitante.perfil.responsable:
        resp = solicitante.perfil.responsable
        resp_perfil = getattr(resp, 'perfil', None)
        responsable_data = {
            'id': resp.id,
            'username': resp.username,
            'email': resp.email,
            'nombre_completo': f"{resp.first_name} {resp.last_name}".strip(),
            'telefono': resp_perfil.telefono if resp_perfil else None,
            'is_staff': resp.is_staff,
            'is_active': resp.is_active
        }

    payload = {
        'event': 'requisicion_finalizada',
        'requisicion': req_data,
        'articulos': articulos,
        'solicitante': solicitante_data,
        'responsable': responsable_data
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"Webhook de requisición {requisicion.cr8ca_requisicion} enviado exitosamente a {url}")
        return True
    except Exception as e:
        logger.error(f"Error al enviar webhook de requisición {requisicion.cr8ca_requisicion}: {str(e)}")
        return False
