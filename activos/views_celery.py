import os
import uuid
from django.shortcuts import render
from django.http import JsonResponse
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.contrib.auth.decorators import login_required, user_passes_test
from .tasks import import_activos_task
from celery.result import AsyncResult

@login_required
@user_passes_test(lambda u: u.is_staff)
def celery_import_activos_view(request):
    """Vista principal para subir el archivo e iniciar la tarea de Celery."""
    if request.method == 'POST' and request.FILES.get('file'):
        myfile = request.FILES['file']
        file_name = myfile.name
        file_format = file_name.split('.')[-1].lower()
        
        if file_format not in ['xlsx', 'xls', 'csv']:
            return JsonResponse({'status': 'error', 'message': 'Formato de archivo no válido. Use Excel o CSV.'}, status=400)

        # Guardar archivo usando el storage por defecto (Local o S3)
        import_id = str(uuid.uuid4())
        path = default_storage.save(
            f'celery_imports/activos_{import_id}.{file_format}', 
            ContentFile(myfile.read())
        )
        
        # Lanzar tarea de Celery (pasando la ruta relativa / llave)
        import_name = request.POST.get('name', f"Importación {file_name}")
        task = import_activos_task.delay(path, file_format, user_id=request.user.id, import_name=import_name)
        
        return JsonResponse({
            'status': 'started',
            'task_id': task.id,
            'message': 'Tarea de importación iniciada en segundo plano.'
        })

    return render(request, 'activos/celery_import_activos.html', {
        'title': 'Importación masiva de Activos con Celery'
    })

@login_required
def celery_import_status(request, task_id):
    """Endpoint para consultar el estado de la tarea de Celery."""
    task_result = AsyncResult(task_id)
    
    response_data = {
        'task_id': task_id,
        'state': task_result.state,
    }
    
    if task_result.state == 'PROGRESS':
        response_data.update(task_result.info)
    elif task_result.state == 'SUCCESS':
        response_data.update(task_result.result)
    elif task_result.state == 'FAILURE':
        response_data['error'] = str(task_result.info)
        
    return JsonResponse(response_data)

@login_required
def celery_cancel_task(request, task_id):
    """Cancela una tarea de Celery en ejecución."""
    from energia.celery import app
    task_result = AsyncResult(task_id)
    
    # Terminar la tarea
    app.control.revoke(task_id, terminate=True, signal='SIGKILL')
    
    return JsonResponse({'status': 'cancelled', 'task_id': task_id})

@login_required
def download_activos_template(request):
    """Genera y descarga una plantilla Excel basada en ActivoResource."""
    from .admin import ActivoResource
    from django.http import HttpResponse
    import tablib
    
    resource = ActivoResource()
    # Obtener cabeceras del resource (excluyendo campos calculados o readonly si se prefiere)
    # Por defecto, export() sin queryset da las cabeceras
    dataset = resource.export(queryset=[])
    
    # Podríamos forzar solo ciertos campos si quisiéramos una plantilla más limpia
    # Pero usar las cabeceras actuales asegura compatibilidad total
    
    export_format = request.GET.get('format', 'xlsx')
    
    if export_format == 'csv':
        response = HttpResponse(dataset.csv, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="plantilla_activos.csv"'
    else:
        response = HttpResponse(dataset.xlsx, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="plantilla_activos.xlsx"'
        
    return response
