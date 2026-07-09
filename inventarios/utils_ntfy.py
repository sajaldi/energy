"""
Utilidades para enviar notificaciones push vía ntfy.sh
"""
import requests
from django.conf import settings


def get_ntfy_url():
    return getattr(settings, 'NTFY_URL', 'https://ntfy.sh')


def get_ntfy_topic():
    return getattr(settings, 'NTFY_TOPIC_SOLICITUDES', 'softcom-ccg-almacen')


def notificar_nueva_solicitud(solicitud):
    """Envía notificación push cuando se crea una solicitud de material."""
    url = f"{get_ntfy_url()}/{get_ntfy_topic()}"
    
    usuario = solicitud.usuario.get_full_name() or solicitud.usuario.username
    items_count = solicitud.items.count()
    ot_info = f" | OT: {solicitud.orden_trabajo.codigo_de_orden}" if solicitud.orden_trabajo else ""
    ubicacion = solicitud.ubicacion_origen.nombre if solicitud.ubicacion_origen else "N/A"
    
    mensaje = f"{usuario} solicita {items_count} material(es) desde {ubicacion}{ot_info}"
    
    try:
        requests.post(
            url,
            data=mensaje.encode('utf-8'),
            headers={
                "Title": f"Nueva Solicitud #{solicitud.id}",
                "Priority": "high",
                "Tags": "package,arrow_down",
                "Click": f"{getattr(settings, 'SITE_URL', 'http://localhost:8000')}/inventarios/mobile/pedidos/{solicitud.id}/",
            },
            timeout=5
        )
    except Exception as e:
        print(f"[NTFY] Error enviando notificación: {e}")
