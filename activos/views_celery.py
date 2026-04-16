import os
import uuid
import time
from django.shortcuts import render
from django.http import JsonResponse
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.cache import cache
from django.views.decorators.csrf import csrf_exempt
from celery.result import AsyncResult
from .tasks import import_activos_task

@login_required
@user_passes_test(lambda u: u.is_staff)
def import_activos_view(request):
    """Renders the upload form for assets background import."""
    from django.contrib import admin
    context = {
        **admin.site.each_context(request),
        'title': 'Importación masiva de Activos (Celery)',
    }
    return render(request, 'activos/celery_import_activos.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
@csrf_exempt
def import_activos_process(request):
    """Triggers the Celery task for importing assets."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    is_confirm = request.POST.get('confirm', '').lower() in ['true', 'on', '1']
    existing_path = request.POST.get('file_path')
    import_file = request.FILES.get('file') # El template de activos usa name="file"

    if not is_confirm:
        if not import_file:
            return JsonResponse({'error': 'No se subió ningún archivo'}, status=400)
            
        file_ext = import_file.name.split('.')[-1].lower()
        temp_name = f'tmp/import_activos_{request.user.id}_{int(time.time())}.{file_ext}'
        
        try:
            path = default_storage.save(temp_name, import_file)
        except Exception as e:
            return JsonResponse({'error': f'Error al guardar archivo: {str(e)}'}, status=500)
    else:
        if not existing_path:
            return JsonResponse({'error': 'Falta la ruta del archivo para confirmar'}, status=400)
        path = existing_path
        file_ext = path.split('.')[-1].lower()
    
    # Limpiar cache de progreso anterior
    cache_key = f"import_activos_progress_{request.user.id}"
    cache.delete(cache_key)
    
    # Trigger Celery task
    v_val = request.POST.get('verification_mode', '').lower()
    verification_mode = v_val in ['true', 'on', '1']
    dry_run = (not verification_mode) and (not is_confirm)
    
    import_name = request.POST.get('name') or f"Importación {import_file.name if import_file else 'Activos'}"
    
    task = import_activos_task.delay(
        path, 
        file_ext, 
        user_id=request.user.id, 
        import_name=import_name,
        verification_mode=verification_mode,
        dry_run=dry_run
    )
    
    return JsonResponse({
        'status': 'started', 
        'task_id': task.id, 
        'dry_run': dry_run,
        'verification_mode': verification_mode
    })

@login_required
def import_activos_progress(request):
    """API to poll progress for assets import."""
    task_id = request.GET.get('task_id')
    if not task_id:
        return JsonResponse({'error': 'Falta task_id'}, status=400)
        
    cache_key = f"import_activos_progress_{request.user.id}"
    progress = cache.get(cache_key, {'status': 'pending', 'percent': 0})
    
    res = AsyncResult(task_id)
    progress['state'] = res.state if res else 'PENDING'
    
    if res.state == 'SUCCESS':
        if isinstance(res.result, dict):
            progress.update(res.result)
        progress['state'] = 'COMPLETED'
        progress['percent'] = 100
    elif res.state == 'FAILURE':
        progress['error'] = str(res.result)
        progress['state'] = 'FAILURE'
        
    return JsonResponse(progress)

@login_required
def celery_cancel_task(request, task_id):
    """Cancela una tarea de Celery en ejecución."""
    from energia.celery import app
    app.control.revoke(task_id, terminate=True, signal='SIGKILL')
    return JsonResponse({'status': 'cancelled', 'task_id': task_id})

@login_required
def download_activos_template(request):
    """Genera y descarga una plantilla Excel basada en ActivoResource."""
    from .admin import ActivoResource
    from django.http import HttpResponse
    import tablib
    
    resource = ActivoResource()
    dataset = resource.export(queryset=[])
    
    export_format = request.GET.get('format', 'xlsx')
    
    if export_format == 'csv':
        response = HttpResponse(dataset.csv, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="plantilla_activos.csv"'
    else:
        response = HttpResponse(dataset.xlsx, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="plantilla_activos.xlsx"'
        
    return response

# --------------------------
# IMPORTACIÓN DE BIENES AFECTOS
# --------------------------
@login_required
@user_passes_test(lambda u: u.is_staff)
def import_bienes_afectos_view(request):
    """Renders the upload form for Bienes Afectos background import."""
    from django.contrib import admin
    context = {
        **admin.site.each_context(request),
        'title': 'Importación masiva de Bienes Afectos (Celery)',
    }
    return render(request, 'activos/celery_import_bienes_afectos.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
@csrf_exempt
def import_bienes_afectos_process(request):
    """Triggers the Celery task for importing genes."""
    from .tasks import import_bienes_afectos_task
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    is_confirm = request.POST.get('confirm', '').lower() in ['true', 'on', '1']
    existing_path = request.POST.get('file_path')
    import_file = request.FILES.get('file')

    if not is_confirm:
        if not import_file:
            return JsonResponse({'error': 'No se subió ningún archivo'}, status=400)
            
        file_ext = import_file.name.split('.')[-1].lower()
        temp_name = f'tmp/import_bienes_{request.user.id}_{int(time.time())}.{file_ext}'
        
        try:
            path = default_storage.save(temp_name, import_file)
        except Exception as e:
            return JsonResponse({'error': f'Error al guardar archivo: {str(e)}'}, status=500)
    else:
        if not existing_path:
            return JsonResponse({'error': 'Falta la ruta del archivo para confirmar'}, status=400)
        path = existing_path
        file_ext = path.split('.')[-1].lower()
    
    # Limpiar cache de progreso anterior
    cache_key = f"import_bienes_progress_{request.user.id}"
    cache.delete(cache_key)
    
    # Trigger Celery task
    v_val = request.POST.get('verification_mode', '').lower()
    verification_mode = v_val in ['true', 'on', '1']
    dry_run = (not verification_mode) and (not is_confirm) # Dry run on first upload
    
    import_name = request.POST.get('name') or f"Importación Bienes {int(time.time())}"
    
    task = import_bienes_afectos_task.delay(
        path, 
        file_ext, 
        user_id=request.user.id, 
        import_name=import_name,
        verification_mode=verification_mode,
        dry_run=dry_run
    )
    
    return JsonResponse({
        'status': 'started', 
        'task_id': task.id, 
        'dry_run': dry_run,
        'verification_mode': verification_mode
    })

@login_required
def import_bienes_afectos_progress(request):
    """API to poll progress for bienes import."""
    task_id = request.GET.get('task_id')
    if not task_id:
        return JsonResponse({'error': 'Falta task_id'}, status=400)
        
    cache_key = f"import_bienes_progress_{request.user.id}"
    progress = cache.get(cache_key, {'status': 'pending', 'percent': 0})
    
    res = AsyncResult(task_id)
    progress['state'] = res.state if res else 'PENDING'
    
    if res.state == 'SUCCESS':
        if isinstance(res.result, dict):
            progress.update(res.result)
        progress['state'] = 'COMPLETED'
        progress['percent'] = 100
    elif res.state == 'FAILURE':
        progress['error'] = str(res.result)
        progress['state'] = 'FAILURE'
        
    return JsonResponse(progress)

@login_required
def download_bienes_template(request):
    """Genera y descarga una plantilla Excel basada en BienAfectoResource."""
    from .resources import BienAfectoResource
    from django.http import HttpResponse
    
    resource = BienAfectoResource()
    dataset = resource.export(queryset=[])
    
    export_format = request.GET.get('format', 'xlsx')
    
    if export_format == 'csv':
        response = HttpResponse(dataset.csv, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="plantilla_bienes_afectos.csv"'
    else:
        response = HttpResponse(dataset.xlsx, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="plantilla_bienes_afectos.xlsx"'
        
    return response

@login_required
@user_passes_test(lambda u: u.is_staff)
def imports_dashboard(request):
    """
    Dashboard unificado para ver el historial de todas las importaciones (Celery).
    """
    from .models import RegistroImportacion
    from django.contrib import admin
    from django.db.models import Count, Q
    
    # Obtener todas las importaciones, ordenadas por fecha descendente
    importaciones = RegistroImportacion.objects.all().select_related('usuario')[:100]
    
    # Estadísticas globales
    stats = RegistroImportacion.objects.aggregate(
        total=Count('id'),
        completadas=Count('id', filter=Q(estado='COMPLETADO')),
        errores=Count('id', filter=Q(estado='ERROR') | Q(filas_error__gt=0))
    )
    
    context = {
        **admin.site.each_context(request),
        'title': 'Dashboard de Importaciones (Celery)',
        'importaciones': importaciones,
        'stats': stats,
    }
    return render(request, 'activos/import_dashboard.html', context)

# --------------------------
# IMPORTACIÓN DE CATEGORÍAS
# --------------------------
@login_required
@user_passes_test(lambda u: u.is_staff)
def import_categorias_view(request):
    """Renders the upload form for Category background import."""
    from django.contrib import admin
    context = {
        **admin.site.each_context(request),
        'title': 'Importación masiva de Categorías (Activos)',
    }
    return render(request, 'activos/celery_import_categorias.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
@csrf_exempt
def import_categorias_process(request):
    """Triggers the Celery task for importing categories."""
    from .tasks import import_categorias_task
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    import_file = request.FILES.get('file')
    if not import_file:
        return JsonResponse({'error': 'No se subió ningún archivo'}, status=400)
            
    file_ext = import_file.name.split('.')[-1].lower()
    temp_name = f'tmp/import_categorias_activos_{request.user.id}_{int(time.time())}.{file_ext}'
    
    try:
        path = default_storage.save(temp_name, import_file)
    except Exception as e:
        return JsonResponse({'error': f'Error al guardar archivo: {str(e)}'}, status=500)
    
    cache_key = f"import_categorias_progress_{request.user.id}"
    cache.delete(cache_key)
    
    import_name = request.POST.get('name') or f"Importación Categorías {import_file.name}"
    
    task = import_categorias_task.delay(path, file_ext, user_id=request.user.id, import_name=import_name)
    
    return JsonResponse({'status': 'started', 'task_id': task.id})

@login_required
def import_categorias_progress(request):
    """API to poll progress for category import."""
    task_id = request.GET.get('task_id')
    if not task_id:
        return JsonResponse({'error': 'Falta task_id'}, status=400)
        
    cache_key = f"import_categorias_progress_{request.user.id}"
    progress = cache.get(cache_key, {'status': 'pending', 'percent': 0})
    
    res = AsyncResult(task_id)
    if res.state == 'SUCCESS':
        if isinstance(res.result, dict):
            progress.update(res.result)
        progress['state'] = 'COMPLETED'
        progress['percent'] = 100
    elif res.state == 'FAILURE':
        progress['error'] = str(res.result)
        progress['state'] = 'FAILURE'
    else:
        progress['state'] = res.state
        
    return JsonResponse(progress)

@login_required
def download_categorias_template(request):
    """Genera y descarga una plantilla Excel para Categorías de Activos."""
    from .admin import CategoriaResource
    from django.http import HttpResponse
    
    resource = CategoriaResource()
    dataset = resource.export(queryset=[])
    
    export_format = request.GET.get('format', 'xlsx')
    
    if export_format == 'csv':
        response = HttpResponse(dataset.csv, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="plantilla_categorias_activos.csv"'
    else:
        response = HttpResponse(dataset.xlsx, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="plantilla_categorias_activos.xlsx"'
        
    return response


# ==================================
# SUPER FILTRO DE ACTIVOS
# ==================================

def _get_descendant_ids(model_class, parent_ids):
    """Recursively collects all descendant IDs for hierarchical models (Ubicacion/Familia)."""
    all_ids = set(parent_ids)
    queue = list(parent_ids)
    while queue:
        children = list(model_class.objects.filter(padre_id__in=queue).values_list('id', flat=True))
        new_children = [c for c in children if c not in all_ids]
        all_ids.update(new_children)
        queue = new_children
    return list(all_ids)


def _build_tree(model_class):
    """Builds a flat list with depth info for hierarchical rendering.
    Uses an in-memory approach to prevent N+1 queries and recursion loops.
    """
    # Bring all records to memory
    all_items = list(model_class.objects.all().order_by('nombre'))
    
    # Map by ID and by Parent ID
    item_map = {item.id: item for item in all_items}
    children_map = {}
    
    for item in all_items:
        pid = item.padre_id if hasattr(item, 'padre_id') else getattr(item, 'padre_id', None)
        if pid not in children_map:
            children_map[pid] = []
        children_map[pid].append(item)
    
    result = []
    visited = set()
    
    def traverse(node_id, depth=0):
        # Prevent loops
        if node_id in visited:
            return
        visited.add(node_id)
        
        children = children_map.get(node_id, [])
        for child in children:
            has_children = child.id in children_map and len(children_map[child.id]) > 0
            
            # Efficiently build path
            curr = child
            path_names = [curr.nombre]
            safe_visit = {curr.id}
            while getattr(curr, 'padre_id', None):
                curr = item_map.get(curr.padre_id)
                if not curr or curr.id in safe_visit:
                    break
                safe_visit.add(curr.id)
                path_names.append(curr.nombre)
                
            path_str = ' → '.join(reversed(path_names))
            
            result.append({
                'value': child.id,
                'label': child.nombre,
                'depth': depth,
                'has_children': has_children,
                'ruta': path_str,
            })
            traverse(child.id, depth + 1)
            
    # Start tree building from roots (padre_id == None)
    traverse(None, depth=0)
    
    return result


@login_required
@user_passes_test(lambda u: u.is_staff)
def superfilter_options(request):
    """Retorna las opciones disponibles para los dropdowns del super filtro."""
    from .models import Activo, Ubicacion, Familia, Marca, Modelo
    
    estados = [{'value': k, 'label': v} for k, v in Activo.ESTADO_CHOICES]
    
    # Hierarchical ubicaciones
    ubicacion_opts = _build_tree(Ubicacion)
    
    # Hierarchical familias
    familia_opts = _build_tree(Familia)
    
    marcas = list(Marca.objects.order_by('nombre').values_list('id', 'nombre'))
    marcas = [{'value': m[0], 'label': m[1]} for m in marcas]
    
    modelos = list(Modelo.objects.select_related('marca').order_by('nombre').values('id', 'nombre', 'marca__id', 'marca__nombre'))
    modelos = [{'value': m['id'], 'label': f"{m['marca__nombre']} - {m['nombre']}", 'marca_id': m['marca__id']} for m in modelos]
    
    return JsonResponse({
        'estados': estados,
        'ubicaciones': ubicacion_opts,
        'familias': familia_opts,
        'marcas': marcas,
        'modelos': modelos,
    })


@login_required
@user_passes_test(lambda u: u.is_staff)
def superfilter_query(request):
    """Ejecuta el filtrado de activos según los criterios recibidos (POST JSON)."""
    import json
    from .models import Activo
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    qs = Activo.objects.select_related('modelo__marca', 'ubicacion', 'familia').all()
    
    # Apply filters
    if body.get('estado'):
        qs = qs.filter(estado__in=body['estado'])
    if body.get('ubicacion'):
        from .models import Ubicacion
        expanded_ids = _get_descendant_ids(Ubicacion, body['ubicacion'])
        qs = qs.filter(ubicacion_id__in=expanded_ids)
    if body.get('familia'):
        qs = qs.filter(familia_id__in=body['familia'])
    if body.get('marca'):
        qs = qs.filter(modelo__marca_id__in=body['marca'])
    if body.get('modelo'):
        qs = qs.filter(modelo_id__in=body['modelo'])
    if body.get('busqueda'):
        q = body['busqueda']
        from django.db.models import Q
        qs = qs.filter(Q(nombre__icontains=q) | Q(codigo_interno__icontains=q) | Q(serie__icontains=q))
    
    total = qs.count()
    
    # Pagination
    page = int(body.get('page', 1))
    per_page = int(body.get('per_page', 50))
    offset = (page - 1) * per_page
    
    activos = qs.order_by('-creado_en')[offset:offset + per_page]
    
    rows = []
    for a in activos:
        rows.append({
            'id': a.id,
            'codigo': a.codigo_interno,
            'nombre': a.nombre,
            'estado': a.get_estado_display(),
            'estado_raw': a.estado,
            'ubicacion': a.ubicacion.get_ruta_completa() if a.ubicacion else '—',
            'familia': str(a.familia) if a.familia else '—',
            'marca': a.modelo.marca.nombre if a.modelo and a.modelo.marca else '—',
            'modelo': a.modelo.nombre if a.modelo else '—',
        })
    
    return JsonResponse({
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page,
        'rows': rows,
    })


@login_required
@user_passes_test(lambda u: u.is_staff)
def superfilter_export(request):
    """(Asíncrono) Inicia la generación del Excel en segundo plano."""
    import json
    from .models import ReporteGenerado
    from .tasks import generar_reporte_activos_task
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    reporte = ReporteGenerado.objects.create(
        usuario=request.user,
        nombre="Exportación de Activos (Super Filtro)",
        estado='PENDIENTE'
    )
    
    task = generar_reporte_activos_task.delay(reporte.id, filtros=body)
    reporte.task_id = task.id
    reporte.save(update_fields=['task_id'])
    
    return JsonResponse({
        'status': 'ok',
        'reporte_id': reporte.id,
        'message': 'El reporte se está procesando en segundo plano.'
    })

@login_required
@user_passes_test(lambda u: u.is_staff)
def superfilter_reportes(request):
    """Devuelve la lista de reportes generados por el usuario."""
    from .models import ReporteGenerado
    
    reportes = ReporteGenerado.objects.filter(usuario=request.user).order_by('-creado_en')[:20]
    
    data = []
    for r in reportes:
        data.append({
            'id': str(r.id),
            'nombre': r.nombre,
            'estado': r.estado,
            'fecha': r.creado_en.strftime('%Y-%m-%d %H:%M'),
            'archivo_url': r.archivo.url if r.archivo else None,
            'detalles_error': r.detalles_error,
        })
        
    return JsonResponse({'reportes': data})

@login_required
@user_passes_test(lambda u: u.is_staff)
def superfilter_reportes_cancelar(request):
    """Cancela un reporte que esté en progreso o pendiente."""
    from .models import ReporteGenerado
    from energia.celery import app as celery_app
    import json
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
        
    try:
        body = json.loads(request.body)
        reporte_id = body.get('id')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
    try:
        reporte = ReporteGenerado.objects.get(id=reporte_id, usuario=request.user)
        if reporte.estado in ['PENDIENTE', 'PROCESANDO'] and reporte.task_id:
            # Revocar la tarea
            celery_app.control.revoke(reporte.task_id, terminate=True)
            reporte.estado = 'CANCELADO'
            reporte.detalles_error = 'Cancelado por el usuario.'
            reporte.save(update_fields=['estado', 'detalles_error'])
            return JsonResponse({'status': 'ok', 'message': 'Reporte cancelado exitosamente.'})
        else:
            return JsonResponse({'status': 'error', 'message': 'El reporte no se puede cancelar en este estado o no tiene task_id.'}, status=400)
    except ReporteGenerado.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Reporte no encontrado'}, status=404)


@login_required
@user_passes_test(lambda u: u.is_staff)
def superfilter_vistas(request):
    """CRUD for saved filter views."""
    import json
    from .models import VistaGuardada
    
    if request.method == 'GET':
        vistas = list(VistaGuardada.objects.filter(usuario=request.user).values('id', 'nombre', 'filtros', 'creada_en'))
        for v in vistas:
            v['creada_en'] = v['creada_en'].strftime('%Y-%m-%d %H:%M')
        return JsonResponse({'vistas': vistas})
    
    elif request.method == 'POST':
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
        nombre = body.get('nombre', '').strip()
        filtros = body.get('filtros', {})
        
        if not nombre:
            return JsonResponse({'error': 'El nombre es requerido'}, status=400)
        
        vista = VistaGuardada.objects.create(
            nombre=nombre,
            usuario=request.user,
            filtros=filtros,
        )
        return JsonResponse({'id': vista.id, 'nombre': vista.nombre, 'status': 'created'})
    
    elif request.method == 'DELETE':
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
        vista_id = body.get('id')
        deleted, _ = VistaGuardada.objects.filter(id=vista_id, usuario=request.user).delete()
        return JsonResponse({'status': 'deleted' if deleted else 'not_found'})
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)
