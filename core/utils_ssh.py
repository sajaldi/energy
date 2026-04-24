import paramiko
import json
from django.conf import settings

def get_ssh_client():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    # Use settings if available, else fallback to hardcoded (for demonstration)
    host = getattr(settings, 'COOLIFY_SSH_HOST', '181.115.47.107')
    port = getattr(settings, 'COOLIFY_SSH_PORT', 3456)
    username = getattr(settings, 'COOLIFY_SSH_USER', 'vboxuser')
    password = getattr(settings, 'COOLIFY_SSH_PASSWORD', 'PasswordRoot07')
    
    ssh.connect(hostname=host, port=port, username=username, password=password, timeout=10)
    return ssh

def get_coolify_containers():
    """Obtiene los repositorios/contenedores de Coolify listando los contenedores Docker."""
    ssh = None
    try:
        ssh = get_ssh_client()
        # Comando para listar contenedores con un formato fácil de parsear, incluyendo labels
        command = 'docker ps --format "{{.ID}}|{{.Names}}|{{.Status}}|{{.Image}}|{{.Labels}}"'
        stdin, stdout, stderr = ssh.exec_command(command)
        output = stdout.read().decode('utf-8').strip()
        
        containers = []
        if output:
            lines = output.split('\n')
            for line in lines:
                parts = line.split('|')
                if len(parts) >= 4:
                    labels_str = parts[4] if len(parts) > 4 else ""
                    
                    # Intentar extraer un nombre más amigable de las etiquetas de Coolify
                    friendly_name = ""
                    # Mapeo de posibles etiquetas que usa Coolify v4 para el nombre
                    label_keys = [
                        "coolify.serviceName=", 
                        "coolify.resourceName=", 
                        "coolify.application.name=",
                        "coolify.service.name="
                    ]
                    
                    for key in label_keys:
                        if key in labels_str:
                            for part in labels_str.split(','):
                                if part.startswith(key):
                                    friendly_name = part.split('=')[1]
                                    break
                            if friendly_name:
                                break
                    
                    application_id = ""
                    for part in labels_str.split(','):
                        if part.startswith("coolify.applicationId="):
                            application_id = part.split('=')[1]
                            break
                    
                    containers.append({
                        'id': parts[0],
                        'name': parts[1],
                        'friendly_name': friendly_name,
                        'application_id': application_id,
                        'status': parts[2],
                        'image': parts[3]
                    })
        return containers
    except Exception as e:
        print(f"Error SSH al obtener contenedores: {e}")
        return []
    finally:
        if ssh:
            ssh.close()

def get_coolify_deploy_logs(application_id):
    """Obtiene los logs de despliegue (build) de la base de datos de Coolify."""
    ssh = None
    try:
        ssh = get_ssh_client()
        # Consultar el último despliegue para esta aplicación
        # La tabla application_deployment_queues contiene los logs en formato JSON
        cmd = f"docker exec coolify-db psql -U coolify -d coolify -t -c \"SELECT logs FROM application_deployment_queues WHERE application_id = '{application_id}' ORDER BY id DESC LIMIT 1;\""
        stdin, stdout, stderr = ssh.exec_command(cmd)
        raw_logs = stdout.read().decode('utf-8').strip()
        
        if not raw_logs:
            return "No se encontraron logs de despliegue para esta aplicación."
            
        try:
            logs_json = json.loads(raw_logs)
            formatted_logs = ""
            for entry in logs_json:
                output = entry.get('output', '')
                formatted_logs += f"{output}\n"
            return formatted_logs
        except:
            return raw_logs # Retornar crudo si no es JSON válido
    except Exception as e:
        return f"Error al obtener logs de despliegue: {e}"
    finally:
        if ssh:
            ssh.close()

def redeploy_container(container_id):
    """Reinicia un contenedor asumiendo que esa es la estrategia de redeploy."""
    ssh = None
    try:
        ssh = get_ssh_client()
        command = f'docker restart {container_id}'
        stdin, stdout, stderr = ssh.exec_command(command)
        output = stdout.read().decode('utf-8').strip()
        err = stderr.read().decode('utf-8').strip()
        return {'success': not bool(err), 'output': output, 'error': err}
    except Exception as e:
        return {'success': False, 'error': str(e)}
    finally:
        if ssh:
            ssh.close()

def get_container_logs(container_id, tail=200):
    """Obtiene los últimos N logs de un contenedor."""
    ssh = None
    try:
        ssh = get_ssh_client()
        command = f'docker logs --tail {tail} {container_id}'
        stdin, stdout, stderr = ssh.exec_command(command)
        out = stdout.read().decode('utf-8')
        err = stderr.read().decode('utf-8')
        # Docker suele mezclar stdout y stderr para los logs, retornamos ambos juntos
        return f"{out}\n{err}".strip()
    except Exception as e:
        return f"Error al obtener logs: {str(e)}"
    finally:
        if ssh:
            ssh.close()

def execute_command_stream(command):
    """Ejecuta un comando y genera un stream de salida en tiempo real."""
    ssh = None
    try:
        ssh = get_ssh_client()
        stdin, stdout, stderr = ssh.exec_command(command, get_pty=True)
        
        # Leemos línea por línea
        while True:
            line = stdout.readline()
            if not line:
                break
            yield line
            
        # También capturamos errores si los hay al final o durante
        err = stderr.read().decode('utf-8')
        if err:
            yield f"\nERROR: {err}"
            
    except Exception as e:
        yield f"Error de conexión SSH: {str(e)}"
    finally:
        if ssh:
            ssh.close()
