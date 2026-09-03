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
            'orden_trabajo': solicitud.orden_trabajo.codigo_de_orden if solicitud.orden_trabajo else "N/A",
            'ot_id': solicitud.orden_trabajo.id if solicitud.orden_trabajo else 0,
            'comentarios': solicitud.comentarios_solicitud or "",
            'items': items,
            'url_admin': f"{settings.SITE_URL}/admin/inventarios/solicitudmaterial/{solicitud.id}/change/",
            'url_app': f"{settings.SITE_URL}/inventarios/mobile/pedidos/{solicitud.id}/",
            'url_almacen': f"{settings.SITE_URL}/admin/?gs_order={solicitud.id}",
        }

        # Enviar el webhook
        response = requests.post(webhook_url, json=data, timeout=5)
        response.raise_for_status()
        
        logger.info(f"Notificación enviada a n8n para la solicitud #{solicitud.id}")
        return True
    except Exception as e:
        logger.error(f"Error al enviar notificación a n8n por solicitud #{solicitud.id}: {e}")
        return False

def notify_n8n_despacho_material(solicitud):
    """
    Envía una notificación a n8n cuando se despacha una solicitud de materiales.
    Indica que los materiales ya están listos para ser retirados.
    """
    webhook_url = getattr(settings, 'N8N_SOLICITUD_WEBHOOK_URL', None)
    if not webhook_url:
        return False

    try:
        perfil = getattr(solicitud.usuario, 'perfil', None)
        telefono = perfil.telefono if perfil else "N/A"

        items_entregados = []
        for mov in solicitud.items.filter(estado='APROBADO'):
            items_entregados.append({
                'material_id': mov.material.id,
                'material': mov.material.nombre,
                'sku': mov.material.sku,
                'cantidad': int(mov.cantidad),
                'cantidad_solicitada': int(mov.cantidad_solicitada),
                'unidad': mov.material.unidad_medida.nombre if mov.material.unidad_medida else "Unidad",
                'comentarios': mov.comentarios or "",
            })

        data = {
            'event': 'solicitud_material_despachada',
            'solicitud_id': solicitud.id,
            'fecha_solicitud': solicitud.fecha_solicitud.isoformat() if solicitud.fecha_solicitud else "",
            'fecha_entrega': solicitud.fecha_entrega.isoformat() if solicitud.fecha_entrega else "",
            'usuario_solicitante': solicitud.usuario.username,
            'usuario_nombre': f"{solicitud.usuario.first_name} {solicitud.usuario.last_name}".strip(),
            'usuario_email': solicitud.usuario.email,
            'usuario_telefono': telefono,
            'almacenista': solicitud.entregado_por.get_full_name() if solicitud.entregado_por else "Sistema",
            'ubicacion_almacen': solicitud.ubicacion_origen.nombre if solicitud.ubicacion_origen else "Almacén",
            'orden_trabajo': solicitud.orden_trabajo.codigo_de_orden if solicitud.orden_trabajo else "N/A",
            'comentarios_almacen': solicitud.comentarios_almacen or "",
            'items': items_entregados,
            'total_materiales': len(items_entregados),
            'url_app': f"{settings.SITE_URL}/inventarios/mobile/pedidos/{solicitud.id}/",
        }

        response = requests.post(webhook_url, json=data, timeout=5)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Error en webhook de despacho para solicitud #{solicitud.id}: {e}")
        return False

def notify_n8n_solicitud_autorizacion(solicitud, jefe):
    """
    Envía una notificación a n8n cuando se crea una nueva solicitud de materiales
    que requiere autorización del jefe inmediato.
    """
    webhook_url = getattr(settings, 'N8N_SOLICITUD_WEBHOOK_URL', None)
    if not webhook_url:
        logger.info("N8N_SOLICITUD_WEBHOOK_URL no configurado. Saltando notificación de autorización.")
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

        # Datos del jefe
        jefe_perfil = getattr(jefe, 'perfil', None)
        jefe_telefono = jefe_perfil.telefono if jefe_perfil else "N/A"

        # Preparar datos de la solicitud
        data = {
            'event': 'solicitud_material_autorizacion',
            'solicitud_id': solicitud.id,
            'fecha': solicitud.fecha_solicitud.isoformat(),
            'usuario': solicitud.usuario.username,
            'usuario_nombre': f"{solicitud.usuario.first_name} {solicitud.usuario.last_name}".strip(),
            'ubicacion_origen': solicitud.ubicacion_origen.nombre if solicitud.ubicacion_origen else "N/A",
            'orden_trabajo': solicitud.orden_trabajo.codigo_de_orden if solicitud.orden_trabajo else "N/A",
            'comentarios': solicitud.comentarios_solicitud or "",
            'items': items,
            'jefe_nombre': f"{jefe.first_name} {jefe.last_name}".strip() or jefe.username,
            'jefe_telefono': jefe_telefono,
            'url_api_autorizar': f"{settings.SITE_URL}/inventarios/api/solicitudes/{solicitud.id}/autorizar/",
        }

        # Enviar el webhook
        response = requests.post(webhook_url, json=data, timeout=5)
        response.raise_for_status()
        
        logger.info(f"Notificación de autorización enviada a n8n para la solicitud #{solicitud.id} (Jefe: {data['jefe_nombre']})")
        return True
    except Exception as e:
        logger.error(f"Error al enviar notificación de autorización a n8n por solicitud #{solicitud.id}: {e}")
        return False


POWERAUTOMATE_SOLICITUD_URL = "https://ce675e3ed2704594af019ed8d7d5f6.d7.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/db1b240ffc614eb3a94903f652c3050f/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=QqwOO3oTcQi7uZvHzQ247cn5Ev4oOf1FuieAVhFLmu4"

POWERAUTOMATE_DESPACHO_URL = "https://ce675e3ed2704594af019ed8d7d5f6.d7.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/00d78dda269f477daefd4464162a4af4/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=F_ds80wMf2RdkzyCaDGF2N118z0-vH9azCzyVPkKKac"

# URL del flujo de aprobación en Power Automate. Se lee desde el entorno
# (definida en Coolify como POWERAUTOMATE_APROBACION_URL).
POWERAUTOMATE_APROBACION_URL = getattr(settings, 'POWERAUTOMATE_APROBACION_URL', '')

POWERAUTOMATE_SITE_URL = "https://softcom.ccg.hn"

def _aprobador_dict(solicitud, u, departamento_nombre):
    """Construye el dict de un aprobador con sus enlaces de acción (sin token)."""
    base = f"{POWERAUTOMATE_SITE_URL}/inventarios/api/solicitudes/{solicitud.id}/autorizar/"
    return {
        'user_id': u.id,
        'nombre': (f"{u.first_name} {u.last_name}".strip() or u.username),
        'email': u.email or '',
        'username': u.username,
        'departamento': departamento_nombre or '',
        'url_aprobar': f"{base}?accion=aprobar&aprobador={u.id}",
        'url_rechazar': f"{base}?accion=rechazar&aprobador={u.id}",
    }


def _obtener_aprobadores_solicitud(solicitud, superior=None):
    """
    Devuelve la lista de aprobadores de salida elegibles para autorizar la solicitud.

    Lógica:
    1. Se obtienen los departamentos vinculados a los materiales de la solicitud.
    2. Se listan los PerfilUsuario con aprobador_salidas=True de esos departamentos.
    3. Si ningún material tiene departamentos restringidos o no hay aprobadores
       configurados, se usa como fallback el superior/jefe directo del solicitante.

    Cada elemento: {'nombre', 'email', 'username', 'departamento'}.
    """
    try:
        from core.models import PerfilUsuario
        from .models import Material

        # Departamentos de los materiales solicitados
        material_ids = [mov.material_id for mov in solicitud.items.all() if mov.material_id]
        deptos_ids = set()
        if material_ids:
            for mat in Material.objects.filter(id__in=material_ids).prefetch_related('departamentos'):
                for depto in mat.departamentos.all():
                    deptos_ids.add(depto.id)

        aprobadores = []
        vistos = set()
        if deptos_ids:
            perfiles = PerfilUsuario.objects.filter(
                departamento_id__in=deptos_ids,
                aprobador_salidas=True
            ).select_related('usuario', 'departamento')
            for p in perfiles:
                u = p.usuario
                if not u or u.id in vistos:
                    continue
                vistos.add(u.id)
                aprobadores.append(_aprobador_dict(solicitud, u, p.departamento.nombre if p.departamento else ''))

        # Fallback: si no hay aprobadores configurados, usar el superior directo
        if not aprobadores and superior:
            aprobadores.append(_aprobador_dict(solicitud, superior, ''))

        return aprobadores
    except Exception as e:
        logger.error(f"Error obteniendo aprobadores para solicitud #{getattr(solicitud, 'id', '?')}: {e}")
        return []


def notify_powerautomate_solicitud(solicitud):
    """
    Envía un webhook a Power Automate cuando se crea una solicitud de materiales.
    """
    try:
        items = []
        for mov in solicitud.items.all():
            items.append({
                'material_id': mov.material.id,
                'material_nombre': mov.material.nombre,
                'sku': mov.material.sku,
                'cantidad': int(mov.cantidad_solicitada),
                'unidad': mov.material.unidad_medida.nombre if mov.material.unidad_medida else "Unidad",
            })

        user = solicitud.usuario
        perfil = getattr(user, 'perfil', None)
        jefe_directo = perfil.responsable if perfil else None
        jefe_departamento = perfil.departamento.responsable if perfil and perfil.departamento else None
        superior = jefe_directo or jefe_departamento

        # Construir la lista de aprobadores de salida elegibles para esta solicitud.
        # Se toman los departamentos de los materiales solicitados y se listan los
        # perfiles con aprobador_salidas=True de esos departamentos. Así Power Automate
        # puede enviar el correo de autorización a cualquiera de ellos.
        aprobadores = _obtener_aprobadores_solicitud(solicitud, superior)

        data = {
            'event': 'solicitud_material_created',
            'solicitud_id': solicitud.id,
            'fecha': solicitud.fecha_solicitud.isoformat(),
            'usuario': user.username,
            'usuario_nombre': f"{user.first_name} {user.last_name}".strip(),
            'usuario_email': user.email,
            'superior_nombre': f"{superior.first_name} {superior.last_name}".strip() if superior else '',
            'superior_email': superior.email if superior else '',
            'aprobadores': aprobadores,
            'aprobadores_emails': [a['email'] for a in aprobadores if a.get('email')],
            'ubicacion_origen': solicitud.ubicacion_origen.nombre if solicitud.ubicacion_origen else "N/A",
            'orden_trabajo': solicitud.orden_trabajo.codigo_de_orden if solicitud.orden_trabajo else "N/A",
            'ot_id': solicitud.orden_trabajo.id if solicitud.orden_trabajo else 0,
            'comentarios': solicitud.comentarios_solicitud or "",
            'estado': solicitud.estado,
            'items': items,
            'url_detalle': f"{POWERAUTOMATE_SITE_URL}/inventarios/solicitud/{solicitud.id}/detalle-departamento/",
            'url_api_autorizar': f"{POWERAUTOMATE_SITE_URL}/inventarios/api/solicitudes/{solicitud.id}/autorizar/",
            'url_estado_badge': f"{POWERAUTOMATE_SITE_URL}/inventarios/solicitud/{solicitud.id}/estado-badge.png",
        }

        # Renderizar el HTML del correo YA ARMADO, uno por aprobador.
        # Así Power Automate solo hace: Para = aprobador.email, Cuerpo = aprobador.email_html.
        try:
            from django.template.loader import render_to_string
            from django.utils import timezone as _tz
            fecha_fmt = _tz.localtime(solicitud.fecha_solicitud).strftime('%d/%m/%Y %H:%M') if solicitud.fecha_solicitud else ''
            ctx_base = {
                'solicitud_id': solicitud.id,
                'usuario_nombre': data['usuario_nombre'] or user.username,
                'usuario_email': data['usuario_email'] or '',
                'fecha': fecha_fmt,
                'ubicacion_origen': data['ubicacion_origen'],
                'orden_trabajo': data['orden_trabajo'],
                'comentarios': data['comentarios'],
                'items': items,
                'url_detalle': data['url_detalle'],
                'url_estado_badge': data['url_estado_badge'],
            }
            for ap in aprobadores:
                ctx = dict(ctx_base)
                ctx['aprobador_nombre'] = ap.get('nombre', '')
                ctx['url_aprobar'] = ap.get('url_aprobar', '')
                ctx['url_rechazar'] = ap.get('url_rechazar', '')
                ap['email_html'] = render_to_string('inventarios/email_autorizacion.html', ctx)
        except Exception as e:
            logger.error(f"Error renderizando email_html de aprobadores para solicitud #{solicitud.id}: {e}")

        if not POWERAUTOMATE_APROBACION_URL:
            logger.warning("POWERAUTOMATE_APROBACION_URL no configurada. Se omite el webhook de aprobación.")
            return False

        response = requests.post(POWERAUTOMATE_APROBACION_URL, json=data, timeout=10)
        response.raise_for_status()
        logger.info(f"Webhook Power Automate (aprobación) enviado para solicitud #{solicitud.id}")
        return True
    except Exception as e:
        logger.error(f"Error en webhook Power Automate para solicitud #{solicitud.id}: {e}")
        return False

def _aprobadores_por_departamento(nombre_departamento):
    """
    Devuelve los usuarios aprobadores (aprobador_salidas=True) que pertenecen a un
    departamento por nombre (ej. 'Almacenes'). Comparación case-insensitive.
    """
    try:
        from core.models import PerfilUsuario
        perfiles = PerfilUsuario.objects.filter(
            departamento__nombre__iexact=nombre_departamento,
            aprobador_salidas=True
        ).select_related('usuario', 'departamento')
        resultado = []
        vistos = set()
        for p in perfiles:
            u = p.usuario
            if not u or u.id in vistos:
                continue
            vistos.add(u.id)
            resultado.append(u)
        return resultado
    except Exception as e:
        logger.error(f"Error obteniendo aprobadores del departamento '{nombre_departamento}': {e}")
        return []


def notify_powerautomate_almacen(solicitud, nombre_departamento="Almacenes"):
    """
    Notifica (informativo) a los aprobadores del departamento de almacén que una
    solicitud fue autorizada y está lista para despacho.

    - Solo envía a los usuarios con aprobador_salidas=True del departamento indicado.
    - Cada aprobador recibe su correo ya armado en 'email_html'.
    - No hay acción de aprobar/rechazar: es una notificación.
    """
    try:
        url = getattr(settings, 'POWERAUTOMATE_DESPACHO_ALMACEN_URL', '')
        if not url:
            logger.warning("POWERAUTOMATE_DESPACHO_ALMACEN_URL no configurada. Se omite la notificación al almacén.")
            return False

        aprobadores_users = _aprobadores_por_departamento(nombre_departamento)
        if not aprobadores_users:
            logger.info(f"Sin aprobadores en el departamento '{nombre_departamento}'. No se notifica al almacén (solicitud #{solicitud.id}).")
            return False

        items = []
        for mov in solicitud.items.all():
            items.append({
                'material_id': mov.material.id,
                'material_nombre': mov.material.nombre,
                'sku': mov.material.sku,
                'cantidad': int(mov.cantidad_solicitada),
                'unidad': mov.material.unidad_medida.nombre if mov.material.unidad_medida else "Unidad",
            })

        user = solicitud.usuario
        autorizado_por = ''
        if solicitud.autorizado_por:
            autorizado_por = (f"{solicitud.autorizado_por.first_name} {solicitud.autorizado_por.last_name}".strip()
                              or solicitud.autorizado_por.username)

        from django.utils import timezone as _tz
        fecha_aut = ''
        if solicitud.fecha_autorizacion:
            fecha_aut = _tz.localtime(solicitud.fecha_autorizacion).strftime('%d/%m/%Y %H:%M')

        url_detalle = f"{POWERAUTOMATE_SITE_URL}/inventarios/solicitud/{solicitud.id}/detalle-departamento/"

        aprobadores = []
        for u in aprobadores_users:
            aprobadores.append({
                'user_id': u.id,
                'nombre': (f"{u.first_name} {u.last_name}".strip() or u.username),
                'email': u.email or '',
                'username': u.username,
            })

        # Renderizar el correo por aprobador de almacén
        try:
            from django.template.loader import render_to_string
            ctx_base = {
                'solicitud_id': solicitud.id,
                'usuario_nombre': (f"{user.first_name} {user.last_name}".strip() or user.username),
                'usuario_email': user.email or '',
                'ubicacion_origen': solicitud.ubicacion_origen.nombre if solicitud.ubicacion_origen else "N/A",
                'orden_trabajo': solicitud.orden_trabajo.codigo_de_orden if solicitud.orden_trabajo else "N/A",
                'comentarios': solicitud.comentarios_solicitud or "",
                'autorizado_por': autorizado_por,
                'fecha_autorizacion': fecha_aut,
                'items': items,
                'url_detalle': url_detalle,
            }
            for ap in aprobadores:
                ctx = dict(ctx_base)
                ctx['aprobador_nombre'] = ap.get('nombre', '')
                ap['email_html'] = render_to_string('inventarios/email_despacho_almacen.html', ctx)
        except Exception as e:
            logger.error(f"Error renderizando email_html de almacén para solicitud #{solicitud.id}: {e}")

        data = {
            'event': 'solicitud_material_lista_despacho',
            'solicitud_id': solicitud.id,
            'estado': solicitud.estado,
            'usuario_nombre': ctx_base['usuario_nombre'],
            'usuario_email': ctx_base['usuario_email'],
            'autorizado_por': autorizado_por,
            'fecha_autorizacion': fecha_aut,
            'ubicacion_origen': ctx_base['ubicacion_origen'],
            'orden_trabajo': ctx_base['orden_trabajo'],
            'comentarios': ctx_base['comentarios'],
            'items': items,
            'aprobadores': aprobadores,
            'aprobadores_emails': [a['email'] for a in aprobadores if a.get('email')],
            'url_detalle': url_detalle,
        }

        response = requests.post(url, json=data, timeout=10)
        response.raise_for_status()
        logger.info(f"Webhook Power Automate (almacén) enviado para solicitud #{solicitud.id}")
        return True
    except Exception as e:
        logger.error(f"Error en webhook Power Automate (almacén) para solicitud #{solicitud.id}: {e}")
        return False


def notify_powerautomate_recoleccion(solicitud):
    """
    Notifica al SOLICITANTE que su orden fue despachada y está lista para recolección.
    Envía el correo ya armado (email_html) al correo del solicitante.
    """
    try:
        url = getattr(settings, 'POWERAUTOMATE_RECOLECCION_URL', '')
        if not url:
            logger.warning("POWERAUTOMATE_RECOLECCION_URL no configurada. Se omite la notificación de recolección.")
            return False

        user = solicitud.usuario
        if not user or not user.email:
            logger.info(f"Solicitud #{solicitud.id}: el solicitante no tiene email. Se omite notificación de recolección.")
            return False

        items = []
        for mov in solicitud.items.all():
            items.append({
                'material_id': mov.material.id,
                'material_nombre': mov.material.nombre,
                'sku': mov.material.sku,
                'cantidad': int(mov.cantidad_solicitada),
                'unidad': mov.material.unidad_medida.nombre if mov.material.unidad_medida else "Unidad",
            })

        solicitante_nombre = (f"{user.first_name} {user.last_name}".strip() or user.username)
        url_detalle = f"{POWERAUTOMATE_SITE_URL}/inventarios/solicitud/{solicitud.id}/detalle-departamento/"
        ubicacion_origen = solicitud.ubicacion_origen.nombre if solicitud.ubicacion_origen else "N/A"
        orden_trabajo = solicitud.orden_trabajo.codigo_de_orden if solicitud.orden_trabajo else "N/A"

        email_html = ''
        try:
            from django.template.loader import render_to_string
            email_html = render_to_string('inventarios/email_recoleccion.html', {
                'solicitud_id': solicitud.id,
                'solicitante_nombre': solicitante_nombre,
                'ubicacion_origen': ubicacion_origen,
                'orden_trabajo': orden_trabajo,
                'items': items,
                'url_detalle': url_detalle,
            })
        except Exception as e:
            logger.error(f"Error renderizando email_html de recolección para solicitud #{solicitud.id}: {e}")

        data = {
            'event': 'solicitud_material_lista_recoleccion',
            'solicitud_id': solicitud.id,
            'estado': solicitud.estado,
            'solicitante_nombre': solicitante_nombre,
            'solicitante_email': user.email,
            'ubicacion_origen': ubicacion_origen,
            'orden_trabajo': orden_trabajo,
            'items': items,
            'email_html': email_html,
            'url_detalle': url_detalle,
        }

        response = requests.post(url, json=data, timeout=10)
        response.raise_for_status()
        logger.info(f"Webhook Power Automate (recolección) enviado para solicitud #{solicitud.id}")
        return True
    except Exception as e:
        logger.error(f"Error en webhook Power Automate (recolección) para solicitud #{solicitud.id}: {e}")
        return False


def notify_powerautomate_entrega(solicitud):
    """
    Notifica al SOLICITANTE que la entrega de su solicitud fue CONFIRMADA en el
    almacén. Incluye las cantidades exactas entregadas, el nombre del receptor y
    la foto de la entrega (URL absoluta).
    Envía el correo ya armado (email_html) al correo del solicitante.
    """
    try:
        url = getattr(settings, 'POWERAUTOMATE_ENTREGA_URL', '')
        if not url:
            logger.warning("POWERAUTOMATE_ENTREGA_URL no configurada. Se omite la notificación de entrega confirmada.")
            return False

        user = solicitud.usuario
        if not user or not user.email:
            logger.info(f"Solicitud #{solicitud.id}: el solicitante no tiene email. Se omite notificación de entrega.")
            return False

        # Cantidades exactas entregadas (movimientos ya liquidados/entregados)
        items = []
        for mov in solicitud.items.all():
            if mov.estado == 'RECHAZADO':
                continue
            items.append({
                'material_id': mov.material.id,
                'material_nombre': mov.material.nombre,
                'sku': mov.material.sku,
                'cantidad': int(mov.cantidad),
                'unidad': mov.material.unidad_medida.nombre if mov.material.unidad_medida else "Unidad",
            })

        solicitante_nombre = (f"{user.first_name} {user.last_name}".strip() or user.username)
        url_detalle = f"{POWERAUTOMATE_SITE_URL}/inventarios/solicitud/{solicitud.id}/detalle-departamento/"
        ubicacion_origen = solicitud.ubicacion_origen.nombre if solicitud.ubicacion_origen else "N/A"
        orden_trabajo = solicitud.orden_trabajo.codigo_de_orden if solicitud.orden_trabajo else "N/A"
        recibe_nombre = getattr(solicitud, 'recibe_nombre', '') or ''

        entregado_por = ''
        if solicitud.entregado_por:
            entregado_por = (f"{solicitud.entregado_por.first_name} {solicitud.entregado_por.last_name}".strip()
                             or solicitud.entregado_por.username)

        from django.utils import timezone as _tz
        fecha_entrega = ''
        if solicitud.fecha_entrega:
            fecha_entrega = _tz.localtime(solicitud.fecha_entrega).strftime('%d/%m/%Y %H:%M')

        # URL pública de la foto de entrega (endpoint sin login, apto para correo).
        # No usamos .url porque devuelve la URL firmada/interna de MinIO
        # (localhost:9000 / host interno), inaccesible desde el cliente de correo.
        foto_url = ''
        try:
            if getattr(solicitud, 'foto_entrega', None):
                foto_url = f"{POWERAUTOMATE_SITE_URL}/inventarios/solicitud/{solicitud.id}/foto-entrega.jpg"
        except Exception:
            foto_url = ''

        email_html = ''
        try:
            from django.template.loader import render_to_string
            email_html = render_to_string('inventarios/email_entrega_confirmada.html', {
                'solicitud_id': solicitud.id,
                'solicitante_nombre': solicitante_nombre,
                'ubicacion_origen': ubicacion_origen,
                'orden_trabajo': orden_trabajo,
                'items': items,
                'recibe_nombre': recibe_nombre,
                'entregado_por': entregado_por,
                'fecha_entrega': fecha_entrega,
                'foto_url': foto_url,
                'url_detalle': url_detalle,
            })
        except Exception as e:
            logger.error(f"Error renderizando email_html de entrega para solicitud #{solicitud.id}: {e}")

        data = {
            'event': 'solicitud_material_entrega_confirmada',
            'solicitud_id': solicitud.id,
            'estado': solicitud.estado,
            'solicitante_nombre': solicitante_nombre,
            'solicitante_email': user.email,
            'ubicacion_origen': ubicacion_origen,
            'orden_trabajo': orden_trabajo,
            'recibe_nombre': recibe_nombre,
            'entregado_por': entregado_por,
            'fecha_entrega': fecha_entrega,
            'foto_url': foto_url,
            'items': items,
            'email_html': email_html,
            'url_detalle': url_detalle,
        }

        response = requests.post(url, json=data, timeout=10)
        response.raise_for_status()
        logger.info(f"Webhook Power Automate (entrega confirmada) enviado para solicitud #{solicitud.id}")
        return True
    except Exception as e:
        logger.error(f"Error en webhook Power Automate (entrega confirmada) para solicitud #{solicitud.id}: {e}")
        return False


def notify_powerautomate_despacho(solicitud):
    """
    Envía un webhook a Power Automate cuando se despacha una solicitud de materiales.
    """
    try:
        items = []
        for mov in solicitud.items.filter(estado='APROBADO'):
            items.append({
                'material_id': mov.material.id,
                'material_nombre': mov.material.nombre,
                'sku': mov.material.sku,
                'cantidad': int(mov.cantidad),
                'unidad': mov.material.unidad_medida.nombre if mov.material.unidad_medida else "Unidad",
            })

        user = solicitud.usuario
        perfil = getattr(user, 'perfil', None)

        data = {
            'event': 'solicitud_material_despachada',
            'solicitud_id': solicitud.id,
            'fecha_entrega': solicitud.fecha_entrega.isoformat() if solicitud.fecha_entrega else "",
            'usuario': user.username,
            'usuario_nombre': f"{user.first_name} {user.last_name}".strip(),
            'usuario_email': user.email,
            'usuario_telefono': perfil.telefono if perfil else "",
            'almacenista': solicitud.entregado_por.get_full_name() if solicitud.entregado_por else "Sistema",
            'ubicacion_almacen': solicitud.ubicacion_origen.nombre if solicitud.ubicacion_origen else "Almacén",
            'orden_trabajo': solicitud.orden_trabajo.codigo_de_orden if solicitud.orden_trabajo else "N/A",
            'comentarios_almacen': solicitud.comentarios_almacen or "",
            'items': items,
            'url_detalle': f"{POWERAUTOMATE_SITE_URL}/inventarios/mobile/pedidos/{solicitud.id}/",
        }

        response = requests.post(POWERAUTOMATE_DESPACHO_URL, json=data, timeout=10)
        response.raise_for_status()
        logger.info(f"Webhook Power Automate despacho enviado para solicitud #{solicitud.id}")
        return True
    except Exception as e:
        logger.error(f"Error en webhook Power Automate despacho para solicitud #{solicitud.id}: {e}")
        return False
