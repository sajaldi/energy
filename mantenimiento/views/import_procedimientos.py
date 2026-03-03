import time
import os
from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from celery.result import AsyncResult
from ..tasks import import_procedimientos_task

@staff_member_required
def import_procedimientos_background(request):
    """Renderiza la vista de carga de archivo."""
    from django.contrib import admin
    context = {
        **admin.site.each_context(request),
        'title': 'Importación masiva de Procedimientos y Pasos',
    }
    return render(request, 'admin/mantenimiento/procedimiento/import_background.html', context)

@staff_member_required
@csrf_exempt
def import_procedimientos_process(request):
    """Inicia la tarea de Celery."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    is_confirm = request.POST.get('confirm', '').lower() in ['true', 'on', '1']
    existing_path = request.POST.get('file_path')
    import_file = request.FILES.get('import_file')

    if not is_confirm:
        if not import_file:
            return JsonResponse({'error': 'No se subió ningún archivo'}, status=400)
            
        file_ext = import_file.name.split('.')[-1].lower()
        temp_name = f'tmp/import_procedimientos_{request.user.id}_{int(time.time())}.{file_ext}'
        
        try:
            path = default_storage.save(temp_name, import_file)
        except Exception as e:
            return JsonResponse({'error': f'Error al guardar archivo: {str(e)}'}, status=500)
    else:
        if not existing_path:
            return JsonResponse({'error': 'Falta ruta de archivo'}, status=400)
        path = existing_path
        file_ext = path.split('.')[-1].lower()
    
    # Limpiar caché previo
    cache_key = f"import_procedimientos_progress_{request.user.id}"
    cache.delete(cache_key)
    
    verification_mode = request.POST.get('verification_mode', '').lower() in ['true', 'on', '1']
    dry_run = (not verification_mode) and (not is_confirm)
    
    import_name = request.POST.get('name') or f"Procedimientos: {import_file.name if import_file else os.path.basename(path)}"
    
    task = import_procedimientos_task.delay(
        path, 
        file_ext, 
        user_id=request.user.id, 
        verification_mode=verification_mode,
        dry_run=dry_run,
        import_name=import_name
    )
    
    return JsonResponse({
        'status': 'started', 
        'task_id': task.id, 
        'dry_run': dry_run,
        'verification_mode': verification_mode
    })

@staff_member_required
def import_procedimientos_progress(request):
    """API para consultar progreso."""
    task_id = request.GET.get('task_id')
    if not task_id:
        return JsonResponse({'error': 'Falta task_id'}, status=400)
        
    cache_key = f"import_procedimientos_progress_{request.user.id}"
    progress = cache.get(cache_key, {'status': 'pending', 'percent': 0})
    
    res = AsyncResult(task_id)
    if res:
        progress['celery_state'] = res.state
        if res.state == 'SUCCESS':
            if isinstance(res.result, dict):
                progress.update(res.result)
            progress['percent'] = 100
        elif res.state == 'FAILURE':
            progress['error'] = str(res.result)
            
    return JsonResponse(progress)
