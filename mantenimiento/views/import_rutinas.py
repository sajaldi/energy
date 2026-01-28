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
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    import_file = request.FILES.get('import_file')
    if not import_file:
        return JsonResponse({'error': 'No file uploaded'}, status=400)
    
    # Save file to temporary storage using chunks
    path = default_storage.save(temp_name, import_file)
    
    # Trigger Celery task
    verification_mode = request.POST.get('verification_mode') == 'true'
    task = import_rutinas_task.delay(path, file_ext, user_id=request.user.id, verification_mode=verification_mode)
    
    return JsonResponse({'task_id': task.id})

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
