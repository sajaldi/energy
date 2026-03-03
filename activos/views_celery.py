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
