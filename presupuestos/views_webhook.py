from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from .models import Requisicion
from .utils_documentos import generate_requisicion_pdf
import json
import logging

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
                    pdf_url = request.build_absolute_uri(pdf_url)

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

