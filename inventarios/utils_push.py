"""
Envío de notificaciones push a la app móvil (Expo Push Notifications).
Los dispositivos registran su token en PerfilUsuario.expo_push_token vía la API móvil.
"""
import logging
import requests

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


def _enviar_expo(tokens, titulo, cuerpo, data=None):
    """Envía una notificación push a una lista de tokens Expo."""
    tokens = [t for t in (tokens or []) if t]
    if not tokens:
        return False
    mensajes = [{
        'to': t,
        'sound': 'default',
        'title': titulo,
        'body': cuerpo,
        'data': data or {},
    } for t in tokens]
    try:
        resp = requests.post(
            EXPO_PUSH_URL,
            json=mensajes,
            headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
            timeout=10,
        )
        resp.raise_for_status()
        logger.info(f"Push Expo enviada a {len(tokens)} dispositivo(s): {titulo}")
        return True
    except Exception as e:
        logger.error(f"Error enviando push Expo: {e}")
        return False


def _tokens_de_usuarios(usuarios):
    """Extrae los tokens push de una lista de usuarios."""
    tokens = []
    for u in usuarios:
        perfil = getattr(u, 'perfil', None)
        tok = getattr(perfil, 'expo_push_token', None) if perfil else None
        if tok:
            tokens.append(tok)
    return tokens


def push_a_aprobadores(solicitud):
    """Notifica a los aprobadores del departamento del solicitante: hay una solicitud por autorizar."""
    try:
        from core.models import PerfilUsuario
        perfil = getattr(solicitud.usuario, 'perfil', None)
        departamento = getattr(perfil, 'departamento', None)
        if not departamento:
            return False
        perfiles = PerfilUsuario.objects.filter(
            departamento=departamento, aprobador_salidas=True
        ).exclude(expo_push_token__isnull=True).exclude(expo_push_token='')
        tokens = [p.expo_push_token for p in perfiles if p.expo_push_token]
        return _enviar_expo(
            tokens,
            'Nueva solicitud por autorizar',
            f'{solicitud.solicitante_nombre} solicitó materiales (#{solicitud.id}).',
            {'tipo': 'aprobacion', 'solicitud_id': solicitud.id},
        )
    except Exception as e:
        logger.error(f"Error en push_a_aprobadores #{getattr(solicitud, 'id', '?')}: {e}")
        return False


def push_a_almacen(solicitud):
    """Notifica a los aprobadores del grupo/departamento Almacenes: solicitud lista para despacho."""
    try:
        from core.models import PerfilUsuario
        perfiles = PerfilUsuario.objects.filter(
            departamento__nombre__iexact='Almacenes', aprobador_salidas=True
        ).exclude(expo_push_token__isnull=True).exclude(expo_push_token='')
        tokens = [p.expo_push_token for p in perfiles if p.expo_push_token]
        return _enviar_expo(
            tokens,
            'Solicitud lista para despacho',
            f'La solicitud #{solicitud.id} fue aprobada y está lista para despachar.',
            {'tipo': 'despacho', 'solicitud_id': solicitud.id},
        )
    except Exception as e:
        logger.error(f"Error en push_a_almacen #{getattr(solicitud, 'id', '?')}: {e}")
        return False


def push_a_solicitante(solicitud):
    """Notifica al solicitante: su pedido está listo para recolección."""
    try:
        tokens = _tokens_de_usuarios([solicitud.usuario])
        return _enviar_expo(
            tokens,
            'Tu pedido está listo',
            f'La solicitud #{solicitud.id} está lista para recolección en el almacén.',
            {'tipo': 'recoleccion', 'solicitud_id': solicitud.id},
        )
    except Exception as e:
        logger.error(f"Error en push_a_solicitante #{getattr(solicitud, 'id', '?')}: {e}")
        return False
