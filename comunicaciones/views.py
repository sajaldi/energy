from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.utils import timezone
import json

from .models import Comunicado, TipoComunicado, Destinatario, AdjuntoComunicado
from activos.models import Activo
from django.contrib.auth.models import User


@login_required
def api_tipos_comunicado(request):
    """Retorna los tipos de comunicado disponibles."""
    tipos = TipoComunicado.objects.all().order_by('nombre')
    return JsonResponse({'tipos': [{'id': t.id, 'nombre': t.nombre, 'codigo': t.codigo} for t in tipos]})

@csrf_exempt
@login_required
def api_create_transmittal(request):
    """
    API para crear un transmittal (Envío formal de activos/documentos).
    Recibe JSON con:
    - asunto
    - cuerpo
    - destinatarios (lista de IDs de usuarios)
    - activos_ids (lista de IDs de activos a adjuntar)
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    
    try:
        data = json.loads(request.body)
        
        asunto = data.get('asunto')
        cuerpo = data.get('cuerpo', '')
        destinatarios_ids = data.get('destinatarios', []) # Lista de IDs de usuarios
        activos_ids = data.get('activos_ids', []) # Lista de IDs de activos
        
        if not asunto or not destinatarios_ids:
            return JsonResponse({'status': 'error', 'message': 'Faltan datos obligatorios (asunto, destinatarios)'}, status=400)
            
        with transaction.atomic():
            # 1. Obtener o crear tipo "Transmittal"
            tipo_transmittal, _ = TipoComunicado.objects.get_or_create(
                codigo='TRS',
                defaults={'nombre': 'Transmittal'}
            )
            
            # 2. Crear Comunicado
            comunicado = Comunicado.objects.create(
                tipo=tipo_transmittal,
                asunto=asunto,
                cuerpo=cuerpo,
                remitente=request.user,
                estado='ENVIADO', # Se envía inmediatamente
                fecha_envio=timezone.now()
            )
            # El save() del modelo genera el consecutivo automáticamente
            
            # 3. Crear Destinatarios
            for user_id in destinatarios_ids:
                try:
                    user = User.objects.get(pk=user_id)
                    Destinatario.objects.create(
                        comunicado=comunicado,
                        usuario=user,
                        tipo='PARA'
                    )
                except User.DoesNotExist:
                    continue
                    
            # 4. Adjuntar Activos
            count_activos = 0
            for activo_id in activos_ids:
                try:
                    activo = Activo.objects.get(pk=activo_id)
                    AdjuntoComunicado.objects.create(
                        comunicado=comunicado,
                        activo=activo
                    )
                    count_activos += 1
                except Activo.DoesNotExist:
                    continue
            
            return JsonResponse({
                'status': 'success',
                'message': 'Transmittal enviado exitosamente',
                'consecutivo': comunicado.consecutivo,
                'activos_adjuntos': count_activos
            })
            
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def lista_transmittals(request):
    """
    Lista todos los comunicados tipo Transmittal (enviados y recibidos)
    """
    # Transmittals enviados por mí
    enviados = Comunicado.objects.filter(
        remitente=request.user, 
        tipo__codigo='TRS'
    ).order_by('-fecha_envio')
    
    # Transmittals recibidos por mí
    recibidos = Comunicado.objects.filter(
        destinatarios__usuario=request.user,
        tipo__codigo='TRS'
    ).order_by('-fecha_envio')
    
    context = {
        'enviados': enviados,
        'recibidos': recibidos
    }
    return render(request, 'comunicaciones/lista_transmittals.html', context)

@login_required
def detalle_transmittal(request, comunicado_id):
    """
    Ver detalle de un Transmittal específico con sus activos adjuntos
    """
    transmittal = get_object_or_404(Comunicado, pk=comunicado_id)
    
    # Verificar permisos (solo remitente o destinatarios pueden ver)
    es_destinatario = transmittal.destinatarios.filter(usuario=request.user).exists()
    if transmittal.remitente != request.user and not es_destinatario:
        # Opcional: Permitir ver a staff/admin
        if not request.user.is_staff:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("No tienes permiso para ver este Transmittal")
            
    # Marcar como leído si soy destinatario
    if es_destinatario:
        destinatario = transmittal.destinatarios.get(usuario=request.user)
        if not destinatario.leido:
            destinatario.leido = True
            destinatario.fecha_leido = timezone.now()
            destinatario.save()
            
    context = {
        'transmittal': transmittal,
        'adjuntos': transmittal.adjuntos.all().select_related('activo', 'documento_revision', 'activo__ubicacion'),
        'destinatarios': transmittal.destinatarios.all().select_related('usuario')
    }
    return render(request, 'comunicaciones/detalle_transmittal.html', context)
