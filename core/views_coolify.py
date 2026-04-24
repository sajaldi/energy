from django.shortcuts import render
from django.http import JsonResponse, StreamingHttpResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import user_passes_test
from .utils_ssh import get_coolify_containers, redeploy_container, get_container_logs, execute_command_stream

@user_passes_test(lambda u: u.is_superuser)
def coolify_dashboard(request):
    """Renderiza la vista principal del Dashboard de Coolify."""
    containers = get_coolify_containers()
    return render(request, 'core/coolify_dashboard.html', {'containers': containers})

@user_passes_test(lambda u: u.is_superuser)
def coolify_redeploy(request):
    """Endpoint para iniciar el stream de redeploy."""
    container_id = request.GET.get('container_id')
    if not container_id:
        return JsonResponse({'status': 'error', 'message': 'ID de contenedor requerido.'}, status=400)
    
    # Usamos docker restart por ahora, o podrías usar un comando de coolify si lo conoces
    command = f'docker restart {container_id}'
    
    def stream():
        yield f"Iniciando redeploy de {container_id}...\n"
        for line in execute_command_stream(command):
            yield line
        yield "\nRedeploy finalizado."

    return StreamingHttpResponse(stream(), content_type='text/plain')

@user_passes_test(lambda u: u.is_superuser)
def coolify_stream_logs(request):
    """Endpoint para ver los logs en tiempo real (follow)."""
    container_id = request.GET.get('container_id')
    if not container_id:
        return JsonResponse({'status': 'error', 'message': 'ID de contenedor requerido.'}, status=400)
    
    # Usamos docker logs -f para streaming continuo
    command = f'docker logs -f --tail 100 {container_id}'
    
    return StreamingHttpResponse(execute_command_stream(command), content_type='text/plain')

@user_passes_test(lambda u: u.is_superuser)
def coolify_logs(request):
    """Endpoint AJAX para obtener los logs de un contenedor."""
    container_id = request.GET.get('container_id')
    if not container_id:
        return JsonResponse({'status': 'error', 'message': 'ID de contenedor requerido.'}, status=400)
    
    logs = get_container_logs(container_id)
    return JsonResponse({'status': 'success', 'logs': logs})

@user_passes_test(lambda u: u.is_superuser)
def coolify_build_logs(request):
    """Endpoint para obtener los logs de construcción (build) de Coolify."""
    application_id = request.GET.get('application_id')
    if not application_id:
        return JsonResponse({'status': 'error', 'message': 'ID de aplicación requerido.'}, status=400)
    
    from .utils_ssh import get_coolify_deploy_logs
    logs = get_coolify_deploy_logs(application_id)
    return JsonResponse({'status': 'success', 'logs': logs})
