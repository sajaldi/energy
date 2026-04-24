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
        # Comando para listar contenedores con un formato fácil de parsear
        command = 'docker ps --format "{{.ID}}|{{.Names}}|{{.Status}}|{{.Image}}"'
        stdin, stdout, stderr = ssh.exec_command(command)
        output = stdout.read().decode('utf-8').strip()
        
        containers = []
        if output:
            lines = output.split('\n')
            for line in lines:
                parts = line.split('|')
                if len(parts) >= 4:
                    containers.append({
                        'id': parts[0],
                        'name': parts[1],
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
