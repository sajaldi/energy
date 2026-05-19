# 🔌 Conexión Remota a Base de Datos en VM

Este procedimiento detalla cómo conectar un entorno local de Django a la base de datos PostgreSQL que corre dentro de una Máquina Virtual (VirtualBox/Coolify) alojada en un servidor físico remoto de la planta.

## 📋 1. Preparación en la Máquina Virtual (Destino Final)
Asegurarse de que Postgres acepte conexiones externas y tenga las credenciales correctas.
- **Puerto predeterminado**: `5432`
- **Comando para forzar contraseña de administración**:
  ```bash
  docker exec -it [CONTAINER_ID] psql -U postgres -c "ALTER USER postgres WITH PASSWORD 'clave_elegida';"
  ```
- **Verificar la IP interna de la VM**: `hostname -I` (por ejemplo: `10.30.1.11`)

## 🖥️ 2. Configuración en la Máquina Física (Servidor Intermedio)
Si la VM está en modo NAT o detrás de una IP física corporativa, se debe mapear el puerto usando `netsh` en Windows desde una terminal como Administrador:
```powershell
netsh interface portproxy add v4tov4 listenport=5433 listenaddress=0.0.0.0 connectport=5432 connectaddress=10.30.1.11
```
> [!WARNING]
> **Conflicto de Puertos**: Asegúrate de detener el servicio local de PostgreSQL en el servidor intermedio si este ya está utilizando el puerto mapeado.

## 💻 3. Acceso desde la Computadora de Desarrollo (Local)
Para máxima estabilidad y seguridad, abrimos un túnel SSH seguro desde tu laptop local de desarrollo:
```powershell
ssh -p [PUERTO_SSH] -L 5433:localhost:5432 [USER]@[IP_PUBLICA]
```

## ⚙️ 4. Configuración en Django (settings.py)
Asegura que el entorno local use el puerto del túnel y que la variable `DATABASE_URL` del archivo `.env` no interfiera:

```python
if os.environ.get('DATABASE_URL'):
    # Producción
    DATABASES = {'default': dj_database_url.config(...)}
else:
    # Desarrollo Local con Túnel SSH
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

---
🔙 Volver a [[00_Inicio|Inicio]]
