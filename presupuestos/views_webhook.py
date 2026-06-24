from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from django.conf import settings
from .models import Requisicion
from .utils_documentos import generate_requisicion_pdf
import json
import logging
from .views_import import _registrar_historial

logger = logging.getLogger(__name__)

@csrf_exempt
@require_POST
def requisicion_webhook_update(request):
    """
    Webhook para recibir actualizaciones de estado desde Power Automate.
    
    Payload esperado:
    {
        "numero_requisicion": "REQ-00000-202X",
        "accion": "APROBAR" | "RECHAZAR" | "DENEGAR",
        "comentarios": "Opcional: razón de aprobación/rechazo"
    }
    
    Respuestas:
    - 200: Actualización exitosa
    - 400: Datos inválidos o faltantes
    - 404: Requisición no encontrada
    - 500: Error interno del servidor
    """
    try:
        # Parsear el body JSON
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            logger.error("Webhook recibió JSON inválido")
            return JsonResponse({
                'success': False, 
                'message': 'El payload debe ser un JSON válido'
            }, status=400)
        
        # Validar campos requeridos
        numero_requisicion = data.get('numero_requisicion')
        accion_raw = data.get('accion')
        accion = accion_raw.upper().strip() if accion_raw else ""
        
        comentarios_raw = data.get('comentarios')
        comentarios = comentarios_raw.strip() if comentarios_raw else ""
        
        if not numero_requisicion:
            return JsonResponse({
                'success': False, 
                'message': 'El campo "numero_requisicion" es obligatorio'
            }, status=400)
        
        if not accion:
            return JsonResponse({
                'success': False, 
                'message': 'El campo "accion" es obligatorio'
            }, status=400)
        
        # Buscar la requisición
        requisicion = Requisicion.objects.filter(cr8ca_requisicion=numero_requisicion).first()
        if not requisicion:
            logger.warning(f"Requisición {numero_requisicion} no encontrada en webhook")
            return JsonResponse({
                'success': False, 
                'message': f'La requisición "{numero_requisicion}" no existe en el sistema'
            }, status=404)
        
        # Mapear acción a estado
        # Soportamos APROBAR, RECHAZAR y DENEGAR (alias de RECHAZAR)
        if accion == 'APROBAR':
            nuevo_estado = 'AUTORIZADO'
            tipo_notif = 'SUCCESS'
            mensaje_usuario = 'aprobada'
        elif accion in ['RECHAZAR', 'DENEGAR']:
            nuevo_estado = 'RECHAZADO'
            tipo_notif = 'ERROR'
            mensaje_usuario = 'rechazada'
        else:
            return JsonResponse({
                'success': False, 
                'message': f'Acción desconocida: "{accion}". Valores válidos: APROBAR, RECHAZAR, DENEGAR'
            }, status=400)
        
        # Verificar que la requisición esté en un estado que permita aprobación/rechazo
        if requisicion.estado_requisicion not in ['BORRADOR', 'PENDIENTE', 'EN_REVISION']:
            logger.warning(f"Intento de actualizar requisición {numero_requisicion} en estado {requisicion.estado_requisicion}")
            return JsonResponse({
                'success': False,
                'message': f'La requisición ya está en estado "{requisicion.get_estado_requisicion_display()}". Solo se pueden aprobar/rechazar requisiciones en borrador o pendientes.'
            }, status=400)
        
        # Actualizar estado
        estado_anterior = requisicion.estado_requisicion
        _registrar_historial(requisicion, nuevo_estado,
                             descripcion=f"Webhook Power Automate: {accion}{' - ' + comentarios if comentarios else ''}")
        requisicion.estado_requisicion = nuevo_estado
        
        # Guardar fecha de aprobación si aplica
        if nuevo_estado == 'AUTORIZADO':
            from django.utils import timezone
            requisicion.fecha_aprobacion = timezone.now()
        
        # Agregar comentarios al historial si se proporcionan
        if comentarios:
            from django.utils import timezone
            timestamp = timezone.now().strftime("%Y-%m-%d %H:%M")
            existing_comments = requisicion.cr8ca_comentarios or ""
            nuevo_comentario = f"[{timestamp}] Power Automate ({accion}): {comentarios}"
            
            if existing_comments:
                requisicion.cr8ca_comentarios = f"{existing_comments}\n{nuevo_comentario}"
            else:
                requisicion.cr8ca_comentarios = nuevo_comentario
        
        requisicion.save()
        
        pdf_url = ""
        # SI SE APRUEBA: Generar el documento PDF basado en la plantilla
        if nuevo_estado == 'AUTORIZADO':
            logger.info(f"Generando PDF para requisición aprobada {numero_requisicion}...")
            doc_obj = generate_requisicion_pdf(requisicion)
            if doc_obj and doc_obj.archivo:
                # Intentamos generar la URL absoluta para que n8n la reciba lista
                pdf_url = doc_obj.archivo.url
                if pdf_url.startswith('/'):
                    pdf_url = f"{settings.SITE_URL.rstrip('/')}{pdf_url}"

        logger.info(f"Requisición {numero_requisicion} actualizada de {estado_anterior} a {nuevo_estado} vía webhook")
        
        # CREAR NOTIFICACIÓN FLOTANTE para el usuario solicitante
        if requisicion.usuario_solicitante:
            try:
                from mantenimiento.models import NotificacionMantenimiento
                mensaje_usuario = 'aprobada' if nuevo_estado == 'AUTORIZADO' else 'rechazada'
                tipo_notif = 'SUCCESS' if nuevo_estado == 'AUTORIZADO' else 'ERROR'
                mensaje_notif = f"Tu requisición {numero_requisicion} ha sido {mensaje_usuario}."
                if comentarios:
                    mensaje_notif += f" Comentarios: {comentarios[:100]}"
                
                NotificacionMantenimiento.objects.create(
                    user=requisicion.usuario_solicitante,
                    mensaje=mensaje_notif,
                    tipo=tipo_notif
                )
                logger.info(f"Notificación creada para usuario {requisicion.usuario_solicitante.username}")
            except Exception as e:
                logger.error(f"Error al crear notificación: {str(e)}")

        return JsonResponse({
            'success': True, 
            'message': f'Requisición {numero_requisicion} actualizada exitosamente a estado {nuevo_estado}',
            'data': {
                'numero_requisicion': numero_requisicion,
                'estado_anterior': estado_anterior,
                'estado_nuevo': nuevo_estado,
                'accion': accion,
                'pdf_url': pdf_url
            }
        }, status=200)
    
    except Exception as e:
        logger.exception(f"Error inesperado en webhook: {str(e)}")
        return JsonResponse({
            'success': False, 
            'message': f'Error interno del servidor: {str(e)}'
        }, status=500)

@csrf_exempt
@require_POST
def dynamics_sync_webhook(request):
    """
    Recibe un lote de requisiciones desde Power Automate para sincronización masiva.
    """
    from decimal import Decimal
    from mantenimiento.models import Empresa
    from django.contrib.auth.models import User
    
    try:
        data = json.loads(request.body)
        items = data.get('value', []) if isinstance(data, dict) else data
        
        if not items:
            return JsonResponse({'success': False, 'message': 'No se recibieron datos o el formato es incorrecto.'}, status=400)

        created_count = 0
        updated_count = 0
        linked_providers = 0
        
        priority_map = {
            380160000: 1, # Baja
            380160001: 2, # Normal
            380160002: 3, # Alta
            380160003: 4, # Urgencia
            380160004: 5, # Emergencia
        }
        
        proveedores_cache = {}
        # Por defecto, si es nuevo, asignar a un usuario administrador o sistema
        default_user = User.objects.filter(is_superuser=True).first()

        skipped_count = 0
        for item in items:
            req_id = item.get('cr8ca_requisicionid')
            if not req_id: continue
            
            raw_priority = item.get('cr8ca_prioridad')
            priority = priority_map.get(raw_priority, 2)
            
            proveedor_guid = item.get('_cr8ca_proveedorasignado_value')
            proveedor_obj = None
            if proveedor_guid:
                if proveedor_guid in proveedores_cache:
                    proveedor_obj = proveedores_cache[proveedor_guid]
                else:
                    proveedor_obj = Empresa.objects.filter(dynamics_guid=proveedor_guid).first()
                    if proveedor_obj:
                        proveedores_cache[proveedor_guid] = proveedor_obj
                        linked_providers += 1
            
            defaults = {
                'cr8ca_requisicion': item.get('cr8ca_requisicion'),
                'cr8ca_asunto': item.get('cr8ca_asunto') or 'Sin asunto (Importado Dynamics)',
                'cr8ca_motivo': item.get('cr8ca_motivo') or 'Sin motivo (Importado Dynamics)',
                'cr8ca_comentarios': item.get('cr8ca_comentarios'),
                'cr8ca_totalenarticulos': Decimal(str(item.get('cr8ca_costo') or 0)),
                'cr8ca_prioridad': priority,
                'createdon': item.get('createdon'),
                'proveedor': proveedor_obj,
            }
            
            # 1. Intentar buscar por UUID de Dynamics
            if Requisicion.objects.filter(cr8ca_requisicionid=req_id).exists():
                # Solo nuevos
                skipped_count += 1
                continue
            
            # 2. Verificar si el NOMBRE ya existe
            nombre_req = defaults.get('cr8ca_requisicion')
            if Requisicion.objects.filter(cr8ca_requisicion=nombre_req).exists():
                skipped_count += 1
                continue
                
            # 3. Si es totalmente nueva, crear
            obj = Requisicion.objects.create(
                cr8ca_requisicionid=req_id,
                **defaults
            )
            obj.usuario_solicitante = default_user
            obj.estado_requisicion = 'BORRADOR'
            obj.save()
            from .models import RequisicionHistorial
            RequisicionHistorial.objects.create(
                requisicion=obj, estado_anterior=None,
                estado_nuevo='BORRADOR',
                descripcion="Importada desde Dynamics"
            )
            created_count += 1
        
        msg = f'Sincronización Cloud exitosa. Se importaron {created_count} nuevas requisiciones.'
        if skipped_count > 0:
            msg += f' Se obviaron {skipped_count} ya existentes.'
        msg += f' {linked_providers} proveedores vinculados.'

        return JsonResponse({
            'success': True, 
            'message': msg
        })

    except Exception as e:
        logger.exception(f"Error en dynamics_sync_webhook: {str(e)}")
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

