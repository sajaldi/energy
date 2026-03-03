import time
import os
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.shortcuts import render
from celery.result import AsyncResult
from ..tasks import import_tipos_task
from django.views.decorators.csrf import csrf_exempt

@staff_member_required
def import_categorias_background(request):
    """Renders the upload form for background category import."""
    from django.contrib import admin
    context = {
        **admin.site.each_context(request),
        'title': 'Importación masiva de Tipos (Mantenimiento)',
    }
    return render(request, 'admin/mantenimiento/tipo/import_background.html', context)

@staff_member_required
@csrf_exempt
def import_categorias_process(request):
    """Triggers the Celery task for importing maintenance categories."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    # 1. Recuperar parámetros
    import_file = request.FILES.get('import_file')
    file_path = request.POST.get('file_path')  # Para confirmación de dry_run
    verif_mode = request.POST.get('verification_mode') == 'true'
    is_confirm = request.POST.get('confirm') == 'true'
    
    if not import_file and not file_path:
        return JsonResponse({'error': 'No se subió ningún archivo ni se especificó ruta para confirmar'}, status=400)
            
    if import_file:
        file_ext = import_file.name.split('.')[-1].lower()
        temp_name = f'tmp/import_tipos_mantenimiento_{request.user.id}_{int(time.time())}.{file_ext}'
        try:
            path = default_storage.save(temp_name, import_file)
        except Exception as e:
            return JsonResponse({'error': f'Error al guardar archivo: {str(e)}'}, status=500)
    else:
        # Usamos el path existente enviado por el cliente (confirmación)
        path = file_path
        file_ext = path.split('.')[-1].lower()

    cache_key = f"import_tipos_progress_{request.user.id}"
    cache.delete(cache_key)
    
    import_name = request.POST.get('name') or (import_file.name if import_file else "Importación confirmada")
    
    # Si no es confirmación ni verificación, forzamos dry_run para el primer paso de preview
    # A menos que el usuario lo quiera saltar (pero por consistencia con otros lo mantenemos)
    dry_run = not verif_mode and not is_confirm

    task = import_tipos_task.delay(
        path, 
        file_ext, 
        user_id=request.user.id,
        verification_mode=verif_mode,
        dry_run=dry_run,
        import_name=import_name
    )
    
    return JsonResponse({
        'status': 'started', 
        'task_id': task.id
    })

@staff_member_required
def import_categorias_progress(request):
    """API to poll progress for maintenance category import."""
    task_id = request.GET.get('task_id')
    if not task_id:
        return JsonResponse({'error': 'Falta task_id'}, status=400)
        
    cache_key = f"import_tipos_progress_{request.user.id}"
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
    elif res.state == 'PROGRESS':
        if isinstance(res.info, dict):
            progress.update(res.info)
        progress['state'] = 'PROGRESS'
    else:
        progress['state'] = res.state if res else 'PENDING'
        
    return JsonResponse(progress)

@staff_member_required
def download_categorias_template(request):
    """Generates and downloads an excel template for maintenance tipos."""
    from ..admin import TipoResource
    from django.http import HttpResponse
    
    resource = TipoResource()
    dataset = resource.export(queryset=[])
    
    export_format = request.GET.get('format', 'xlsx')
    
    if export_format == 'csv':
        response = HttpResponse(dataset.csv, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="formato_tipos_mantenimiento.csv"'
    else:
        response = HttpResponse(dataset.xlsx, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="formato_tipos_mantenimiento.xlsx"'
        
    return response
