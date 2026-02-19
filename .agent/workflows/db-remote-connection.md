---
description: Procedimiento para conectar Django local a bases de datos en VMs en Datacenters
---

# Conexión Remota de Base de Datos (Estructura Híbrida)

Este flujo de trabajo detalla cómo conectar un entorno local de Django a una base de datos PostgreSQL que corre dentro de una VM (VirtualBox/Coolify) alojada en un servidor físico remoto.

## 1. Preparación en la Máquina Virtual (Destino Final)
Asegurarse de que Postgres acepte conexiones externas y tenga las credenciales correctas.
- Puerto: `5432`
- Comando para forzar clave: `docker exec -it [CONTAINER_ID] psql -U postgres -c "ALTER USER postgres WITH PASSWORD 'clave_elegida';"`
- Verificar IP interna: `hostname -I` (ej. `10.30.1.11`)

## 2. Configuración en la Máquina Física (Servidor Intermedio)
Si la VM está en modo NAT o detrás de una IP física, usar `netsh` en Windows:
// turbo
```powershell
netsh interface portproxy add v4tov4 listenport=5433 listenaddress=0.0.0.0 connectport=5432 connectaddress=10.30.1.11
```
*Importante: Detener el servicio de Postgres local en la máquina física si usa el mismo puerto.*

## 3. Acceso desde la Computadora de Desarrollo (Local)
Para máxima estabilidad y seguridad, usar un túnel SSH:
```powershell
ssh -p [PUERTO_SSH] -L 5433:localhost:5432 [USER]@[IP_PUBLICA]
```

## 4. Configuración en Django (settings.py)
Asegurar que el entorno local use el puerto del túnel y que la variable `DATABASE_URL` del `.env` no interfiera.

```python
if os.environ.get('DATABASE_URL'):
    # Producción
    DATABASES = {'default': dj_database_url.config(...)}
else:
    # Desarrollo Local con Túnel
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'HOST': '127.0.0.1',
            'PORT': '5433',
            'NAME': 'postgres',
            'USER': 'postgres',
            'PASSWORD': 'clave_elegida',
            'OPTIONS': {'sslmode': 'disable'},
        }
    }
```
