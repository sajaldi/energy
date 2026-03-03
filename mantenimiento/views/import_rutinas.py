import time
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.shortcuts import render
from celery.result import AsyncResult
from ..tasks import import_rutinas_task

from django.views.decorators.csrf import csrf_exempt

@staff_member_required
def import_rutinas_background(request):
    """Renders the upload form for background import."""
    from django.contrib import admin
    context = {
        **admin.site.each_context(request),
        'title': 'Importación masiva de Rutinas (Background)',
    }
    return render(request, 'admin/mantenimiento/rutina/import_background.html', context)

@staff_member_required
@csrf_exempt
def import_rutinas_process(request):
    """Triggers the Celery task for importing routines."""
    import sys
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    is_confirm = request.POST.get('confirm', '').lower() in ['true', 'on', '1']
    existing_path = request.POST.get('file_path')
    import_file = request.FILES.get('import_file')

    # Si NO es confirmación, necesitamos un archivo nuevo obligatoriamente
    if not is_confirm:
        if not import_file:
            return JsonResponse({'error': 'No se subió ningún archivo'}, status=400)
            
        print(f"[DEBUG] [Rutinas] Recibido archivo nuevo: {import_file.name}")
        file_ext = import_file.name.split('.')[-1].lower()
        temp_name = f'tmp/import_rutinas_{request.user.id}_{int(time.time())}.{file_ext}'
        
        try:
            path = default_storage.save(temp_name, import_file)
        except Exception as e:
            return JsonResponse({'error': f'Error al guardar archivo: {str(e)}'}, status=500)
    else:
        # ES UNA CONFIRMACIÓN: Usar el archivo que ya está en el servidor
        if not existing_path:
            return JsonResponse({'error': 'Falta la ruta del archivo para confirmar'}, status=400)
        path = existing_path
        file_ext = path.split('.')[-1].lower()
        print(f"[DEBUG] [Rutinas] Confirmando importación sobre archivo existente: {path}")
    
    # Limpiar cache de progreso anterior para este usuario para evitar persistencia de estados viejos
    cache_key = f"import_rutinas_progress_{request.user.id}"
    cache.delete(cache_key)
    
    # Trigger Celery task
    v_val = request.POST.get('verification_mode', '').lower()
    verification_mode = v_val in ['true', 'on', '1']
    
    # Lógica de Dry Run: SOLO si no es verificación y no es confirmación final
    dry_run = (not verification_mode) and (not is_confirm)
    
    print(f"[DEBUG] [Rutinas] POST: {request.POST}")
    print(f"[DEBUG] [Rutinas] verification_mode={verification_mode}, dry_run={dry_run}, is_confirm={is_confirm}")
    sys.stdout.flush()
    
    import_name = request.POST.get('name') or f"Rutinas: {import_file.name if import_file else os.path.basename(path)}"
    
    task = import_rutinas_task.delay(
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
def import_rutinas_progress(request):
    """API to poll progress for routine import."""
    task_id = request.GET.get('task_id')
    if not task_id:
        return JsonResponse({'error': 'Falta task_id'}, status=400)
        
    cache_key = f"import_rutinas_progress_{request.user.id}"
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
