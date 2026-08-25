"""
Utilidades para enviar notificaciones push vía ntfy.sh + Web Push (personal).
"""
import requests
from django.conf import settings


def get_ntfy_url():
    return getattr(settings, 'NTFY_URL', 'https://ntfy.sh')


def get_ntfy_topic():
    return getattr(settings, 'NTFY_TOPIC_SOLICITUDES', 'softcom-ccg-almacen')


def get_ntfy_topic_aprobacion():
    return getattr(settings, 'NTFY_TOPIC_APROBACION', 'softcom-ccg-aprobacion')


def _send_webpush_to_user(user, title, body, url=None):
    """Envía Web Push personal a un usuario específico."""
    try:
        from webpush import send_user_notification
        payload = {
            "head": title,
            "body": body,
            "icon": "/static/favicon.ico",
        }
        if url:
            payload["url"] = url
        send_user_notification(user=user, payload=payload, ttl=1000)
        print(f"[WEBPUSH] Enviado a {user.username}: {title}")
    except Exception as e:
        print(f"[WEBPUSH] Error enviando a {user.username}: {e}")


def _send_webpush_to_group(group_name, title, body, url=None):
    """Envía Web Push a todos los usuarios de un grupo Django."""
    try:
        from django.contrib.auth.models import Group
        from webpush import send_user_notification
        group = Group.objects.filter(name=group_name).first()
        if not group:
            print(f"[WEBPUSH] Grupo '{group_name}' no existe")
            return
        payload = {
            "head": title,
            "body": body,
            "icon": "/static/favicon.ico",
        }
        if url:
            payload["url"] = url
        for user in group.user_set.filter(is_active=True):
            try:
                send_user_notification(user=user, payload=payload, ttl=1000)
            except Exception:
                pass
        print(f"[WEBPUSH] Enviado a grupo '{group_name}': {title}")
    except Exception as e:
        print(f"[WEBPUSH] Error enviando a grupo: {e}")


def notificar_nueva_solicitud(solicitud):
    """Envía notificación push al almacén cuando una solicitud está lista para despacho."""
    usuario = solicitud.usuario.get_full_name() or solicitud.usuario.username
    items_count = solicitud.items.count()
    ot_info = f" | OT: {solicitud.orden_trabajo.codigo_de_orden}" if solicitud.orden_trabajo else ""
    ubicacion = solicitud.ubicacion_origen.nombre if solicitud.ubicacion_origen else "N/A"
    
    title = f"Nueva Solicitud #{solicitud.id}"
    body = f"{usuario} solicita {items_count} material(es) desde {ubicacion}{ot_info}"
    site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
    link = f"{site_url}/inventarios/mobile/gestion-salidas/?solicitud={solicitud.id}"
    
    # Web Push al grupo Almacenes
    _send_webpush_to_group('Almacenes', title, body, link)
    
    # Fallback ntfy
    url = f"{get_ntfy_url()}/{get_ntfy_topic()}"
    try:
        requests.post(
            url,
            data=body.encode('utf-8'),
            headers={
                "Title": title,
                "Priority": "high",
                "Tags": "package,arrow_down",
                "Click": link,
            },
            timeout=5
        )
    except Exception as e:
        print(f"[NTFY] Error: {e}")


def notificar_pendiente_aprobacion(solicitud):
    """Envía Web Push personal al jefe directo cuando se requiere su autorización."""
    site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
    usuario = solicitud.usuario.get_full_name() or solicitud.usuario.username
    items_count = solicitud.items.count()
    ot_info = f" | OT: {solicitud.orden_trabajo.codigo_de_orden}" if solicitud.orden_trabajo else ""
    
    title = f"Aprobar Solicitud #{solicitud.id}"
    body = f"{usuario} solicita {items_count} material(es){ot_info}. Toca para aprobar."
    
    # Obtener el jefe directo
    perfil = getattr(solicitud.usuario, 'perfil', None)
    jefe = perfil.responsable if perfil else None
    
    link = f"{site_url}/inventarios/mobile/pedidos/{solicitud.id}/"
    
    # Web Push personal al jefe
    if jefe:
        _send_webpush_to_user(jefe, title, body, link)
    
    # Fallback ntfy al canal general de aprobación
    url = f"{get_ntfy_url()}/{get_ntfy_topic_aprobacion()}"
    try:
        requests.post(
            url,
            data=body.encode('utf-8'),
            headers={
                "Title": title,
                "Priority": "high",
                "Tags": "warning,clipboard",
                "Click": link,
            },
            timeout=5
        )
    except Exception as e:
        print(f"[NTFY] Error: {e}")
