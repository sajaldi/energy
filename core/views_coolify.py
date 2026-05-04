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

def _find_celery_container(ssh, service='worker'):
    """Busca el container de Celery por nombre o por comando."""
    # Estrategia 1: buscar por nombre (docker-compose standard)
    search_term = f'celery_{service}' if service in ('worker', 'beat') else 'celery_worker'
    find_cmd = f'docker ps --format "{{{{.Names}}}}" | grep -i "{search_term}" | head -1'
    stdin, stdout, stderr = ssh.exec_command(find_cmd)
    container_name = stdout.read().decode('utf-8').strip()
    if container_name:
        return container_name
    
    # Estrategia 2: buscar por el comando que corre (Coolify renombra los containers)
    celery_cmd = 'celery.*worker' if service == 'worker' else 'celery.*beat'
    find_cmd2 = f'docker ps --format "{{{{.Names}}}}|{{{{.Command}}}}" | grep -iE "{celery_cmd}" | head -1 | cut -d"|" -f1'
    stdin, stdout, stderr = ssh.exec_command(find_cmd2)
    container_name = stdout.read().decode('utf-8').strip()
    if container_name:
        return container_name
    
    # Estrategia 3: buscar por nombre que contenga simplemente "celery"
    find_cmd3 = f'docker ps --format "{{{{.Names}}}}" | grep -i "celery" | head -1'
    stdin, stdout, stderr = ssh.exec_command(find_cmd3)
    return stdout.read().decode('utf-8').strip()

@user_passes_test(lambda u: u.is_superuser)
def celery_logs(request):
    """Endpoint AJAX para obtener los últimos logs del Celery worker."""
    tail = int(request.GET.get('tail', 300))
    service = request.GET.get('service', 'worker')  # 'worker' o 'beat'
    
    from .utils_ssh import get_ssh_client
    ssh = None
    try:
        ssh = get_ssh_client()
        container_name = _find_celery_container(ssh, service)
        
        if not container_name:
            return JsonResponse({'status': 'error', 'message': f'No se encontró contenedor de Celery ({service}). Verifica que esté corriendo en producción.'})
        
        cmd = f'docker logs --tail {tail} {container_name} 2>&1'
        stdin, stdout, stderr = ssh.exec_command(cmd)
        logs = stdout.read().decode('utf-8')
        err = stderr.read().decode('utf-8')
        
        return JsonResponse({
            'status': 'success', 
            'logs': f"{logs}\n{err}".strip(),
            'container': container_name
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})
    finally:
        if ssh:
            ssh.close()

@user_passes_test(lambda u: u.is_superuser)
def celery_stream_logs(request):
    """Endpoint para ver los logs de Celery en tiempo real (streaming)."""
    service = request.GET.get('service', 'worker')
    
    from .utils_ssh import get_ssh_client
    
    def stream():
        ssh = None
        try:
            ssh = get_ssh_client()
            container_name = _find_celery_container(ssh, service)
            
            if not container_name:
                yield f"Error: No se encontró contenedor de Celery ({service}). Verifica que esté corriendo en producción.\n"
                return
            
            yield f"📡 Conectado a: {container_name}\n{'='*60}\n"
            
            cmd = f'docker logs -f --tail 100 {container_name} 2>&1'
            stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True)
            
            while True:
                line = stdout.readline()
                if not line:
                    break
                yield line
        except Exception as e:
            yield f"Error de conexión SSH: {str(e)}\n"
        finally:
            if ssh:
                ssh.close()
    
    return StreamingHttpResponse(stream(), content_type='text/plain')
