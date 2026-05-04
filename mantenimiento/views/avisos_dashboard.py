from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_http_methods
from django.utils import timezone
import json
from ..models import Aviso, OrdenTrabajo, TecnicoPuesto
from core.models import Departamento
from django.contrib.auth.models import User

@staff_member_required
def avisos_kanban_dashboard(request):
    """
    Vista principal estática que renderiza el tablero Kanban de avisos.
    Los datos se cargan dinámicamente mediante la API.
    """
    tecnicos = TecnicoPuesto.objects.filter(disponible=True).select_related('user', 'puesto')
    tecnicos_list = [{'id': t.user.id if t.user else '', 'nombre': f"{t.user.get_full_name() or t.user.username} ({t.puesto.nombre if t.puesto else 'Sin Puesto'})"} for t in tecnicos if t.user]
    
    departamentos = [{'id': d.id, 'nombre': d.nombre} for d in Departamento.objects.all()]
    
    return render(request, 'mantenimiento/avisos_kanban.html', {
        'tecnicos_json': json.dumps(tecnicos_list),
        'departamentos_json': json.dumps(departamentos)
    })

@staff_member_required
@require_http_methods(["GET"])
def api_get_avisos(request):
    """
    Devuelve los avisos agrupados por estado para el Kanban.
    Acepta filtros: search
    """
    search = request.GET.get('search', '').strip()
    
    avisos_qs = Aviso.objects.select_related(
        'ubicacion', 'solicitante', 'responsable', 'falla', 'activo'
    ).order_by('-prioridad', '-creado_en')
    
    if search:
        avisos_qs = avisos_qs.filter(
            descripcion__icontains=search
        ) | avisos_qs.filter(
            ubicacion__nombre__icontains=search
        )
    
    data = {
        'ABIERTO': [],
        'PROCESO': [],
        'CERRADO': [],
        'CANCELADO': []
    }
    
    for aviso in avisos_qs:
        item = {
            'id': aviso.id,
            'titulo': f"AV-{aviso.id}",
            'descripcion': aviso.descripcion,
            'estado': aviso.estado,
            'prioridad': aviso.prioridad,
            'tipo': aviso.tipo,
            'tipo_display': aviso.get_tipo_display(),
            'ubicacion': aviso.ubicacion.nombre if aviso.ubicacion else "Desconocida",
            'activo': aviso.activo.nombre if aviso.activo else "",
            'solicitante': aviso.solicitante.get_full_name() or aviso.solicitante.username if aviso.solicitante else "Sistema",
            'responsable_id': aviso.responsable.id if aviso.responsable else None,
            'responsable_nombre': aviso.responsable.get_full_name() or aviso.responsable.username if aviso.responsable else "Sin asignar",
            'creado_en': aviso.creado_en.strftime("%d/%m/%Y %H:%M"),
            'tiene_foto': bool(aviso.foto),
            'foto_url': aviso.foto.url if aviso.foto else None,
            'falla': aviso.falla.nombre if aviso.falla else "",
        }
        if aviso.estado in data:
            data[aviso.estado].append(item)
            
    return JsonResponse({'status': 'success', 'data': data})

@staff_member_required
@require_http_methods(["POST"])
def api_update_aviso_estado(request, pk):
    """
    Actualiza el estado de un aviso (Drag & Drop en Kanban)
    """
    try:
        payload = json.loads(request.body)
        aviso = get_object_or_404(Aviso, id=pk)
        
        nuevo_estado = payload.get('estado')
        if nuevo_estado in dict(Aviso.ESTADO_CHOICES):
            aviso.estado = nuevo_estado
            if nuevo_estado == 'CERRADO':
                aviso.fecha_cierre = timezone.now()
            elif nuevo_estado != 'CERRADO' and aviso.fecha_cierre is not None:
                aviso.fecha_cierre = None
                
            # Si asignan un nuevo responsable desde el Drag & Drop o modal
            responsable_id = payload.get('responsable_id')
            if responsable_id:
                aviso.responsable_id = responsable_id
                
            aviso.save()
            return JsonResponse({'status': 'success', 'message': f'Aviso {aviso.id} movido a {nuevo_estado}.'})
        else:
            return JsonResponse({'status': 'error', 'message': 'Estado inválido.'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@staff_member_required
@require_http_methods(["POST"])
def api_aviso_create_ot(request, pk):
    """
    Genera una OT Correctiva a partir de un aviso pendiente.
    """
    try:
        payload = json.loads(request.body)
        aviso = get_object_or_404(Aviso, id=pk)
        
        # Validar si ya tiene OT
        ot_existente = OrdenTrabajo.objects.filter(aviso=aviso).first()
        if ot_existente:
            return JsonResponse({'status': 'error', 'message': 'Este aviso ya tiene una Orden de Trabajo asignada.'}, status=400)
        
        tecnico_id = payload.get('tecnico_id')
        tecnico_user = None
        if tecnico_id:
            tecnico_user = User.objects.filter(id=tecnico_id).first()
            
        fecha_inicio_str = payload.get('fecha_inicio')
        if fecha_inicio_str:
            fecha_inicio = timezone.make_aware(timezone.datetime.fromisoformat(fecha_inicio_str))
        else:
            fecha_inicio = timezone.now()
            
        prioridad_ot = payload.get('prioridad', aviso.prioridad)
            
        # Crear OT Correctiva
        nueva_ot = OrdenTrabajo.objects.create(
            aviso=aviso,
            tipo='CORRECTIVA',
            prioridad=prioridad_ot,
            estado='PROGRAMADA' if tecnico_user else 'ESPERA',
            ubicacion=aviso.ubicacion,
            tecnico=tecnico_user,
            inicio_programado=fecha_inicio,
            descripcion_corta=f"Corr.: {aviso.descripcion[:50]}...",
        )
        
        # Opcional: Si el aviso tiene un activo, asignarselo a la OT
        if aviso.activo:
            nueva_ot.activos.add(aviso.activo)
            
        # Actualizar aviso automáticamente a EN PROCESO
        if aviso.estado == 'ABIERTO':
            aviso.estado = 'PROCESO'
            if tecnico_user:
                aviso.responsable = tecnico_user
            aviso.save()
            
        return JsonResponse({'status': 'success', 'message': f'Orden de Trabajo {nueva_ot.codigo_de_orden} creada correctamente.', 'ot_id': nueva_ot.id})
        
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@staff_member_required
@require_http_methods(["POST"])
def api_notify_responsable(request, pk):
    """
    Dispara una notificación al responsable del aviso vía n8n (Celery Task).
    """
    from ..tasks import notify_responsible_n8n
    try:
        # Enviar a Celery para no bloquear el request
        notify_responsible_n8n.delay(pk)
        return JsonResponse({'status': 'success', 'message': 'Proceso de notificación iniciado.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
