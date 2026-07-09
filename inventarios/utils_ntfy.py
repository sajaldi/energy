"""
Utilidades para enviar notificaciones push vía ntfy.sh
"""
import requests
from django.conf import settings


def get_ntfy_url():
    return getattr(settings, 'NTFY_URL', 'https://ntfy.sh')


def get_ntfy_topic():
    return getattr(settings, 'NTFY_TOPIC_SOLICITUDES', 'softcom-ccg-almacen')


def get_ntfy_topic_aprobacion():
    return getattr(settings, 'NTFY_TOPIC_APROBACION', 'softcom-ccg-aprobacion')


def notificar_nueva_solicitud(solicitud):
    """Envía notificación push al almacén cuando una solicitud está lista para despacho."""
    url = f"{get_ntfy_url()}/{get_ntfy_topic()}"
    
    usuario = solicitud.usuario.get_full_name() or solicitud.usuario.username
    items_count = solicitud.items.count()
    ot_info = f" | OT: {solicitud.orden_trabajo.codigo_de_orden}" if solicitud.orden_trabajo else ""
    ubicacion = solicitud.ubicacion_origen.nombre if solicitud.ubicacion_origen else "N/A"
    
    mensaje = f"{usuario} solicita {items_count} material(es) desde {ubicacion}{ot_info}"
    
    try:
        resp = requests.post(
            url,
            data=mensaje.encode('utf-8'),
            headers={
                "Title": f"Nueva Solicitud #{solicitud.id}",
                "Priority": "high",
                "Tags": "package,arrow_down",
                "Click": f"{getattr(settings, 'SITE_URL', 'http://localhost:8000')}/inventarios/mobile/gestion-salidas/?solicitud={solicitud.id}",
            },
            timeout=5
        )
        print(f"[NTFY] Solicitud #{solicitud.id} → almacén: {resp.status_code}")
    except Exception as e:
        print(f"[NTFY] Error enviando a almacén: {e}")


def notificar_pendiente_aprobacion(solicitud):
    """Envía notificación push al canal de aprobación cuando se requiere autorización del jefe."""
    url = f"{get_ntfy_url()}/{get_ntfy_topic_aprobacion()}"
    site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
    
    usuario = solicitud.usuario.get_full_name() or solicitud.usuario.username
    items_count = solicitud.items.count()
    ot_info = f" | OT: {solicitud.orden_trabajo.codigo_de_orden}" if solicitud.orden_trabajo else ""
    
    # Generar token de aprobación
    import hashlib
    token = hashlib.sha256(f"{solicitud.id}-{solicitud.fecha_solicitud}".encode()).hexdigest()[:16]
    
    link_aprobacion = f"{site_url}/inventarios/aprobar/{solicitud.id}/{token}/"
    
    mensaje = (
        f"{usuario} solicita {items_count} material(es){ot_info}\n"
        f"Toca para revisar y aprobar/rechazar."
    )
    
    try:
        resp = requests.post(
            url,
            data=mensaje.encode('utf-8'),
            headers={
                "Title": f"Aprobar Solicitud #{solicitud.id}",
                "Priority": "high",
                "Tags": "warning,clipboard",
                "Click": link_aprobacion,
                "Actions": f"view, Revisar y Aprobar, {link_aprobacion}",
            },
            timeout=5
        )
        print(f"[NTFY] Solicitud #{solicitud.id} → aprobación: {resp.status_code}")
    except Exception as e:
        print(f"[NTFY] Error enviando a aprobación: {e}")
