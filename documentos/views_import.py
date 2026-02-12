import time
import os
import sys
from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from celery.result import AsyncResult
from .tasks import import_comentarios_task

@staff_member_required
def import_comentarios_background(request):
    """Renderiza la vista de carga de archivo."""
    from django.contrib import admin
    context = {
        **admin.site.each_context(request),
        'title': 'Importación masiva de Comentarios',
    }
    return render(request, 'admin/documentos/comentariodocumento/import_background.html', context)

@staff_member_required
@csrf_exempt
def import_comentarios_process(request):
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
        # Guardar en tmp
        temp_name = f'tmp/import_comentarios_{request.user.id}_{int(time.time())}.{file_ext}'
        
        try:
            path = default_storage.save(temp_name, import_file)
        except Exception as e:
            return JsonResponse({'error': f'Error al guardar archivo: {str(e)}'}, status=500)
    else:
        # Confirmación
        if not existing_path:
            return JsonResponse({'error': 'Falta ruta de archivo'}, status=400)
        path = existing_path
        file_ext = path.split('.')[-1].lower()
    
    # Limpiar caché previo
    cache_key = f"import_comentarios_progress_{request.user.id}"
    cache.delete(cache_key)
    
    # Parámetros
    v_val = request.POST.get('verification_mode', '').lower()
    verification_mode = v_val in ['true', 'on', '1']
    
    # Dry Run: Solo si no es verif y no es confirm
    dry_run = (not verification_mode) and (not is_confirm)
    
    task = import_comentarios_task.delay(
        path, 
        file_ext, 
        user_id=request.user.id, 
        verification_mode=verification_mode,
        dry_run=dry_run
    )
    
    return JsonResponse({
        'status': 'started', 
        'task_id': task.id, 
        'dry_run': dry_run,
        'verification_mode': verification_mode
    })

@staff_member_required
def import_comentarios_progress(request):
    """API para consultar progreso."""
    task_id = request.GET.get('task_id')
    if not task_id:
        return JsonResponse({'error': 'Falta task_id'}, status=400)
        
    cache_key = f"import_comentarios_progress_{request.user.id}"
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

@staff_member_required
def download_template(request):
    """Genera plantilla Excel para Comentarios."""
    from .resources import ComentarioDocumentoResource
    from .models import ComentarioDocumento
    
    dataset = ComentarioDocumentoResource().export(queryset=ComentarioDocumento.objects.none())
    response = HttpResponse(dataset.xlsx, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="plantilla_comentarios.xlsx"'
    return response
