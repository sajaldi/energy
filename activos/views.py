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

# --- Vistas para Arbol Interactivo ---

@staff_member_required
def arbol_activos_view(request):
    """Vista principal que renderiza el template del árbol"""
    return render(request, 'activos/arbol_activos.html', {
        'title': 'Explorador de Activos por Ubicación'
    })

@staff_member_required
def api_ubicaciones_root(request):
    from .models import Ubicacion
    roots = Ubicacion.objects.filter(padre__isnull=True).order_by('orden', 'nombre')
    data = []
    for u in roots:
        data.append({
            'id': u.id,
            'nombre': u.nombre,
            'tipo': u.tipo,
            'has_children': u.sub_ubicaciones.exists()
        })
    return JsonResponse(data, safe=False)

@staff_member_required
def api_ubicaciones_children(request, parent_id):
    from .models import Ubicacion
    children = Ubicacion.objects.filter(padre_id=parent_id).order_by('orden', 'nombre')
    data = []
    for u in children:
        data.append({
            'id': u.id,
            'nombre': u.nombre,
            'tipo': u.tipo,
            'has_children': u.sub_ubicaciones.exists()
        })
    return JsonResponse(data, safe=False)

@staff_member_required
def api_ubicacion_detalle(request, ubicacion_id):
    from .models import Ubicacion, Activo
    from django.db.models import Count, Q
    
    try:
        ubicacion = Ubicacion.objects.get(id=ubicacion_id)
    except Ubicacion.DoesNotExist:
        return JsonResponse({'error': 'Ubicación no encontrada'}, status=404)
        
    # Obtener activos de esta ubicación y todas sus descendientes
    descendants = ubicacion.get_descendants(include_self=True)
    activos = Activo.objects.filter(ubicacion__in=descendants).select_related('modelo__categoria__padre', 'modelo__categoria', 'modelo', 'ubicacion')
    
    # Estructura de árbol: Root Name -> { data, subcats: { Sub Name -> [assets] } }
    groups = {}
    total_operativos = 0
    
    for activo in activos:
        # Estado
        if activo.estado == 'OPERATIVO':
            total_operativos += 1

        # Categorización
        cat_directa = activo.modelo.categoria if (activo.modelo and activo.modelo.categoria) else None
        
        # Agrupador Principal (Padre o Directa si no tiene padre)
        # Nota: Asumimos jerarquía de 2 niveles para visualización simple. 
        # Si tiene abuelo, este lógica tomará al padre inmediato como raíz de visualización.
        # Para ser más robustos en "Sistemas", idealmente buscaríamos la raíz, pero esto funciona para "Tipo -> Subtipo".
        cat_root = cat_directa.padre if (cat_directa and cat_directa.padre) else cat_directa
        
        root_name = cat_root.nombre if cat_root else "Otros"
        root_icon = cat_root.icono if cat_root else "cube"
        
        # Subcategoría (Solo si es diferente a la raíz)
        sub_name = cat_directa.nombre if (cat_directa and cat_directa != cat_root) else "_general_"
        
        if root_name not in groups:
            groups[root_name] = {
                'nombre': root_name,
                'icono': root_icon,
                'total_assets': 0,
                'subcats': {} 
            }
            
        groups[root_name]['total_assets'] += 1
        
        if sub_name not in groups[root_name]['subcats']:
            groups[root_name]['subcats'][sub_name] = []
            
        # Serializar activo
        groups[root_name]['subcats'][sub_name].append({
            'id': activo.id,
            'nombre': activo.nombre,
            'codigo': activo.codigo_interno or 'S/C',
            'serie': activo.serie,
            'modelo': activo.modelo.nombre if activo.modelo else None,
            'estado': activo.estado,
            'estado_display': activo.get_estado_display(),
            'ubicacion_nombre': activo.ubicacion.nombre if activo.ubicacion else 'Sin Ubicación',
            'is_child': activo.ubicacion_id != ubicacion.id,
        })

    # Procesar para JSON (Listas ordenadas)
    final_list = []
    for root_key in sorted(groups.keys()):
        g_data = groups[root_key]
        
        # Procesar subcategorías
        subs_list = []
        # Ponemos "_general_" al principio si existe
        if "_general_" in g_data['subcats']:
            subs_list.append({
                'nombre': 'General',
                'is_general': True,
                'activos': g_data['subcats'].pop("_general_")
            })
            
        # El resto ordenado alfabéticamente
        for sub_key in sorted(g_data['subcats'].keys()):
            subs_list.append({
                'nombre': sub_key,
                'is_general': False,
                'activos': g_data['subcats'][sub_key]
            })
            
        final_list.append({
            'nombre': g_data['nombre'],
            'icono': g_data['icono'],
            'total_items': g_data['total_assets'],
            'subcategorias': subs_list
        })
    
    return JsonResponse({
        'ubicacion': {
            'id': ubicacion.id,
            'nombre': ubicacion.nombre,
            'tipo': ubicacion.get_tipo_display(),
            'ruta': ubicacion.get_ruta_completa(),
            'descripcion': ubicacion.descripcion
        },
        'total_activos': activos.count(),
        'activos_operativos': total_operativos,
        'categorias': final_list
    })

@staff_member_required
def api_activo_detalle(request, activo_id):
    from .models import Activo
    
    try:
        activo = Activo.objects.select_related(
            'modelo__marca', 'modelo__categoria', 'ubicacion', 'responsable'
        ).get(id=activo_id)
    except Activo.DoesNotExist:
        return JsonResponse({'error': 'Activo no encontrado'}, status=404)
        
    data = {
        'id': activo.id,
        'nombre': activo.nombre,
        'codigo_interno': activo.codigo_interno,
        'serie': activo.serie,
        'estado': activo.estado,
        'estado_display': activo.get_estado_display(),
        'marca': activo.modelo.marca.nombre if (activo.modelo and activo.modelo.marca) else None,
        'modelo': activo.modelo.nombre if activo.modelo else None,
        'categoria': activo.modelo.categoria.nombre if (activo.modelo and activo.modelo.categoria) else None,
        'ubicacion': activo.ubicacion.ruta_completa if activo.ubicacion else 'Sin Ubicación',
        'responsable': activo.responsable.get_full_name() or activo.responsable.username if activo.responsable else 'Sin Asignar',
        'fecha_compra': activo.fecha_compra.strftime('%d/%m/%Y') if activo.fecha_compra else None,
        'costo': str(activo.costo) if activo.costo else None,
        'descripcion': activo.descripcion,
        'foto_url': activo.foto.url if activo.foto else None,
        'creado_en': activo.creado_en.strftime('%d/%m/%Y'),
        'legacy_ubicacion': activo.ubicacion_legacy
    }
    
    return JsonResponse(data)


@staff_member_required
def mobile_activo_detalle(request, pk):
    """
    Vista detallada de un Activo optimizada para móviles.
    """
    activo = get_object_or_404(Activo.objects.select_related('modelo__marca', 'ubicacion', 'responsable'), pk=pk)
    
    # Obtener OTs relacionadas recientes
    ots_recientes = activo.ordenes_trabajo.all().order_by('-inicio_programado')[:5]
    
    context = {
        'activo': activo,
        'ots_recientes': ots_recientes,
    }
    return render(request, 'activos/mobile_activo_detalle.html', context)


@staff_member_required
def mobile_busqueda_activos(request):
    """
    Buscador de activos optimizado para móviles.
    """
    query = request.GET.get('q', '').strip()
    activos = []
    
    if query:
        activos = Activo.objects.filter(
            models.Q(nombre__icontains=query) | 
            models.Q(codigo_interno__icontains=query) |
            models.Q(serie__icontains=query)
        ).select_related('ubicacion')[:20]
        
        # Si solo hay uno, redirigir directo
        if activos.count() == 1:
            return redirect('activos:mobile_activo_detalle', pk=activos[0].id)
            
    return render(request, 'activos/mobile_busqueda.html', {
        'activos': activos,
        'query': query
    })
