from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from .models import Requisicion
import json

@csrf_exempt
@require_POST
def requisicion_webhook_update(request):
    """
    Webhook para recibir actualizaciones de estado desde Power Automate.
    Payload esperado:
    {
        "numero_requisicion": "REQ-00000-202X",
        "accion": "APROBAR" | "RECHAZAR",
        "comentarios": "Opcional"
    }
    """
    try:
        data = json.loads(request.body)
        numero_requisicion = data.get('numero_requisicion')
        accion = data.get('accion', '').upper()
        comentarios = data.get('comentarios', '')

        if not numero_requisicion:
            return JsonResponse({'success': False, 'message': 'Falta numero_requisicion'}, status=400)

        # Buscar la requisición
        requisicion = Requisicion.objects.filter(cr8ca_requisicion=numero_requisicion).first()
        if not requisicion:
            return JsonResponse({'success': False, 'message': f'Requisición {numero_requisicion} no encontrada'}, status=404)

        # Mapear acción a estado
        if accion == 'APROBAR':
            nuevo_estado = 'AUTORIZADO'
        elif accion == 'RECHAZAR':
            nuevo_estado = 'RECHAZADO'
        else:
            return JsonResponse({'success': False, 'message': f'Acción desconocida: {accion}'}, status=400)

        # Actualizar estado
        requisicion.estado_requisicion = nuevo_estado
        
        # Opcional: Agregar comentarios al historial o campo de comentarios
        if comentarios:
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            existing_comments = requisicion.cr8ca_comentarios or ""
            requisicion.cr8ca_comentarios = f"{existing_comments}\n[{timestamp}] Power Automate ({accion}): {comentarios}".strip()

        requisicion.save()

        # CREAR NOTIFICACIÓN FLOTANTE
        if requisicion.usuario_solicitante:
            from mantenimiento.models import NotificacionMantenimiento
            tipo_notif = 'SUCCESS' if accion == 'APROBAR' else 'ERROR'
            mensaje_notif = f"Tu requisición {numero_requisicion} ha sido {nuevo_estado}."
            
            NotificacionMantenimiento.objects.create(
                user=requisicion.usuario_solicitante,
                mensaje=mensaje_notif,
                tipo=tipo_notif
            )

        return JsonResponse({
            'success': True, 
            'message': f'Requisición {numero_requisicion} actualizada a {nuevo_estado}'
        })

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'JSON inválido'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)
