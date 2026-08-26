"""
Utilidades para enviar notificaciones push vía ntfy.sh + Power Automate (correo personal).
"""
import requests
from django.conf import settings


def get_ntfy_url():
    return getattr(settings, 'NTFY_URL', 'https://ntfy.sh')


def get_ntfy_topic():
    return getattr(settings, 'NTFY_TOPIC_SOLICITUDES', 'softcom-ccg-almacen')


def notificar_nueva_solicitud(solicitud):
    """Envía notificación ntfy al almacén + Power Automate cuando una solicitud está lista."""
    site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
    usuario = solicitud.usuario.get_full_name() or solicitud.usuario.username
    items_count = solicitud.items.count()
    ot_info = f" | OT: {solicitud.orden_trabajo.codigo_de_orden}" if solicitud.orden_trabajo else ""
    ubicacion = solicitud.ubicacion_origen.nombre if solicitud.ubicacion_origen else "N/A"
    
    title = f"Nueva Solicitud #{solicitud.id}"
    body = f"{usuario} solicita {items_count} material(es) desde {ubicacion}{ot_info}"
    link = f"{site_url}/inventarios/mobile/gestion-salidas/?solicitud={solicitud.id}"
    
    # ntfy al canal del almacén
    try:
        requests.post(
            f"{get_ntfy_url()}/{get_ntfy_topic()}",
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
        print(f"[NTFY] Error almacén: {e}")


def notificar_pendiente_aprobacion(solicitud):
    """
    Envía notificación al jefe directo vía Power Automate (correo personal).
    También ntfy al canal personal del jefe.
    """
    site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
    usuario = solicitud.usuario.get_full_name() or solicitud.usuario.username
    items_count = solicitud.items.count()
    ot_info = f" | OT: {solicitud.orden_trabajo.codigo_de_orden}" if solicitud.orden_trabajo else ""
    
    # Obtener jefe directo
    perfil = getattr(solicitud.usuario, 'perfil', None)
    jefe = perfil.responsable if perfil else None
    
    title = f"Aprobar Solicitud #{solicitud.id}"
    body = f"{usuario} solicita {items_count} material(es){ot_info}. Requiere su aprobación."
    link = f"{site_url}/inventarios/mobile/pedidos/{solicitud.id}/"
    
    # 1. Power Automate: correo directo al jefe
    webhook_url = getattr(settings, 'POWER_AUTOMATE_WEBHOOK_URL', '') or getattr(settings, 'POWER_AUTOMATE_INVITATION', '')
    if webhook_url and jefe and jefe.email:
        payload = {
            'email': jefe.email,
            'username': jefe.get_full_name() or jefe.username,
            'tipo': 'aprobacion_material',
            'titulo': title,
            'mensaje': body,
            'solicitante': usuario,
            'items_count': items_count,
            'solicitud_id': solicitud.id,
            'link_aprobacion': link,
        }
        try:
            requests.post(webhook_url, json=payload, timeout=10)
            print(f"[PA] Aprobación solicitud #{solicitud.id} → {jefe.email}")
        except Exception as e:
            print(f"[PA] Error enviando aprobación: {e}")
    
    # 2. ntfy al canal personal del jefe (username)
    if jefe:
        ntfy_topic = f"softcom-{jefe.username}"
        try:
            requests.post(
                f"{get_ntfy_url()}/{ntfy_topic}",
                data=body.encode('utf-8'),
                headers={
                    "Title": title,
                    "Priority": "urgent",
                    "Tags": "warning,clipboard",
                    "Click": link,
                },
                timeout=5
            )
            print(f"[NTFY] Aprobación → {ntfy_topic}")
        except Exception as e:
            print(f"[NTFY] Error canal personal: {e}")


def notificar_aprobadores_salida(solicitud, aprobadores_qs):
    """
    Envía notificación a los aprobadores de salida del departamento vinculado al material.
    Se envía a cada aprobador via Power Automate (correo) y ntfy (push).
    """
    site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
    usuario = solicitud.usuario.get_full_name() or solicitud.usuario.username
    items_count = solicitud.items.count()
    ot_info = f" | OT: {solicitud.orden_trabajo.codigo_de_orden}" if solicitud.orden_trabajo else ""
    
    title = f"Aprobar Solicitud #{solicitud.id}"
    body = f"{usuario} solicita {items_count} material(es){ot_info}. Requiere aprobación de salida."
    link = f"{site_url}/inventarios/mobile/pedidos/{solicitud.id}/"

    webhook_url = getattr(settings, 'POWER_AUTOMATE_WEBHOOK_URL', '') or getattr(settings, 'POWER_AUTOMATE_INVITATION', '')

    for perfil in aprobadores_qs:
        aprobador = perfil.usuario
        depto_nombre = perfil.departamento.nombre if perfil.departamento else "N/A"
        
        # 1. Power Automate: correo al aprobador
        if webhook_url and aprobador.email:
            payload = {
                'email': aprobador.email,
                'username': aprobador.get_full_name() or aprobador.username,
                'tipo': 'aprobacion_material',
                'titulo': title,
                'mensaje': body,
                'solicitante': usuario,
                'items_count': items_count,
                'solicitud_id': solicitud.id,
                'departamento': depto_nombre,
                'link_aprobacion': link,
            }
            try:
                requests.post(webhook_url, json=payload, timeout=10)
                print(f"[PA] Aprobación salida #{solicitud.id} → {aprobador.email} ({depto_nombre})")
            except Exception as e:
                print(f"[PA] Error aprobación salida: {e}")

        # 2. ntfy al canal personal del aprobador
        ntfy_topic = f"softcom-{aprobador.username}"
        try:
            requests.post(
                f"{get_ntfy_url()}/{ntfy_topic}",
                data=body.encode('utf-8'),
                headers={
                    "Title": title,
                    "Priority": "urgent",
                    "Tags": "warning,clipboard",
                    "Click": link,
                },
                timeout=5
            )
            print(f"[NTFY] Aprobación salida → {ntfy_topic} ({depto_nombre})")
        except Exception as e:
            print(f"[NTFY] Error canal aprobador salida: {e}")
