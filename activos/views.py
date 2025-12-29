from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from .models import VisorPlano, PinPlano, Activo
import json
from django.views.decorators.csrf import csrf_exempt
from celery.result import AsyncResult
from django.contrib.admin.views.decorators import staff_member_required

def visor_plano(request, visor_id):
    visor = get_object_or_404(VisorPlano, pk=visor_id)
    # Prefetch activos for performance in the modal
    activos = Activo.objects.all().select_related('modelo__categoria', 'ubicacion').order_by('nombre')
    
    from .models import Categoria, Ubicacion
    from mantenimiento.models import Aviso
    from proyectos.models import Actividad
    
    categorias = Categoria.objects.all().order_by('nombre')
    ubicaciones = Ubicacion.objects.all().order_by('nombre')
    # Solo avisos abiertos o en proceso
    avisos = Aviso.objects.filter(estado__in=['ABIERTO', 'PROCESO']).order_by('-creado_en')
    # Actividades de proyectos pendientes o en progreso
    actividades = Actividad.objects.filter(
        estado__in=['PENDIENTE', 'EN_PROGRESO']
    ).select_related('proyecto').order_by('proyecto__codigo', 'orden')
    proyectos_visor = visor.proyectos.all()
    
    context = {
        'visor': visor,
        'activos': activos,
        'ubicaciones': ubicaciones,
        'categorias': categorias,
        'avisos': avisos,
        'actividades': actividades,
        'proyectos': proyectos_visor,
    }
    
    return render(request, 'activos/visor_plano.html', context)

@csrf_exempt
@staff_member_required
def guardar_pin(request):
    if request.method == 'POST':
        try:
            # Soportar tanto JSON como FormData (para archivos)
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST

            pin_id = data.get('id')
            visor_id = data.get('visor_id')
            activo_id = data.get('activo_id')
            aviso_id = data.get('aviso_id')
            x = float(data.get('x'))
            y = float(data.get('y'))
            color = data.get('color', '#FF0000')
            nota = data.get('nota', '')

            if pin_id and pin_id != 'null':
                pin = get_object_or_404(PinPlano, id=pin_id)
            else:
                pin = PinPlano(visor_id=visor_id)

            if activo_id:
                # Verificar duplicados en el mismo visor
                dup = PinPlano.objects.filter(visor_id=visor_id, activo_id=activo_id).exclude(id=pin.id).first()
                if dup:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'El activo "{dup.activo.nombre}" ya está ubicado en este plano.'
                    }, status=400)
                pin.activo_id = activo_id
            else:
                pin.activo = None
            
            if aviso_id:
                pin.aviso_id = aviso_id
            else:
                pin.aviso = None
            
            # Actividad de proyecto
            actividad_id = data.get('actividad_id')
            if actividad_id:
                pin.actividad_id = actividad_id
            else:
                pin.actividad = None
                
            pin.x = x
            pin.y = y
            pin.color = color
            pin.nota = nota
            pin.save()

            # Guardar fotos si vienen en la petición
            if 'fotos' in request.FILES:
                from .models import PinFoto
                for f in request.FILES.getlist('fotos'):
                    PinFoto.objects.create(pin=pin, imagen=f)

            # Obtener URLs de las fotos
            fotos_urls = [f.imagen.url for f in pin.fotos.all()]

            nombre_label = "Sin asignar"
            icono_label = "location"
            aviso_meta = {}
            
            if pin.actividad:
                nombre_label = pin.actividad.nombre
                icono_label = "construct"
            elif pin.activo:
                nombre_label = pin.activo.nombre
                cat = pin.activo.modelo.categoria if pin.activo.modelo else None
                icono_label = cat.icono if cat else 'cube'
            elif pin.aviso:
                nombre_label = f"AV-{pin.aviso.id}"
                icono_label = "warning"
                aviso_meta = {
                    'prioridad': pin.aviso.get_prioridad_display(),
                    'estado': pin.aviso.get_estado_display(),
                    'solicitante': pin.aviso.solicitante.username if pin.aviso.solicitante else 'Anónimo',
                    'descripcion': pin.aviso.descripcion
                }

            return JsonResponse({
                'status': 'success',
                'pin_id': pin.id,
                'activo_id': pin.activo.id if pin.activo else None,
                'aviso_id': pin.aviso.id if pin.aviso else None,
                'actividad_id': pin.actividad.id if pin.actividad else None,
                'nombre_activo': nombre_label,
                'nombre_actividad': pin.actividad.nombre if pin.actividad else None,
                'codigo_externo': pin.activo.codigo_interno if pin.activo else '',
                'nota': pin.nota,
                'fotos': fotos_urls,
                'icono': icono_label,
                'aviso_meta': aviso_meta
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

@csrf_exempt
def eliminar_pin(request, pin_id):
    if request.method == 'POST':
        pin = get_object_or_404(PinPlano, id=pin_id)
        pin.delete()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=405)

def import_progress(request, task_id):
    """
    API endpoint para obtener el progreso de una tarea de importación Celery.
    """
    task = AsyncResult(task_id)
    
    if task.state == 'PENDING':
        response = {
            'state': task.state,
            'current': 0,
            'total': 1,
            'status': 'Esperando inicio...',
            'percent': 0
        }
    elif task.state == 'PROGRESS':
        response = {
            'state': task.state,
            'current': task.info.get('current', 0),
            'total': task.info.get('total', 1),
            'status': task.info.get('status', ''),
            'current_row': task.info.get('current_row', ''),
            'percent': task.info.get('percent', 0)
        }
    elif task.state == 'SUCCESS':
        response = {
            'state': task.state,
            'current': 100,
            'total': 100,
            'status': 'Completado',
            'percent': 100,
            'result': task.info
        }
    else:  # FAILURE, etc.
        response = {
            'state': task.state,
            'current': 1,
            'total': 1,
            'status': str(task.info),  # Exception info
            'percent': 0
        }
    
    return JsonResponse(response)

@staff_member_required
def get_import_progress(request):
    """
    Retorna información detallada del progreso de importación para el usuario actual.
    Incluye: porcentaje, item actual, conteo procesado, estadísticas y velocidad.
    """
    from django.core.cache import cache
    uid = request.user.id
    
    progress = cache.get(f"import_progress_{uid}", 0)
    current_item = cache.get(f"import_progress_{uid}_current", '')
    processed = cache.get(f"import_progress_{uid}_count", 0)
    stats = cache.get(f"import_progress_{uid}_stats", {'new': 0, 'update': 0, 'skip': 0, 'error': 0})
    start_time = cache.get(f"import_progress_{uid}_start", 0)
    
    # Calcular velocidad (items por segundo)
    import time
    elapsed = time.time() - start_time if start_time else 0
    speed = round(processed / elapsed, 1) if elapsed > 0 else 0
    
    return JsonResponse({
        'progress': progress,
        'current_item': current_item,
        'processed': processed,
        'stats': stats,
        'speed': speed,  # items/segundo
        'elapsed': round(elapsed, 1)
    })
