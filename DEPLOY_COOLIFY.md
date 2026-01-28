# Guía Rápida de Despliegue en Coolify

## Pasos para Desplegar

### 1. Preparar el Repositorio
```bash
# Asegúrate de que estos archivos estén en tu repositorio
git add docker-compose.yml Dockerfile requirements.txt .env.example
git commit -m "Add Coolify deployment configuration"
git push
```

### 2. Configurar en Coolify

1. **Crear Nuevo Proyecto**
   - Ve a tu dashboard de Coolify
   - Click en "New Resource" → "Docker Compose"
   - Conecta tu repositorio Git

2. **Configurar Variables de Entorno**
   En la sección de Environment Variables de Coolify, agrega:
   ```
   DJANGO_DEBUG=False
   SECRET_KEY=<genera-una-clave-segura-aquí>
   DATABASE_URL=postgresql://user:pass@host:5432/dbname
   CELERY_BROKER_URL=redis://redis:6379/0
   CELERY_RESULT_BACKEND=django-db
   ALLOWED_HOSTS=tu-dominio.com,*.coolify.io
   CSRF_TRUSTED_ORIGINS=https://tu-dominio.com
   AWS_S3_ENDPOINT_URL=https://tu-minio-endpoint.com  # O la IP/DNS interna si usas MinIO en Coolify
   ```

3. **Configurar Base de Datos**
   - Si no tienes PostgreSQL, créalo en Coolify:
     - New Resource → Database → PostgreSQL
     - Copia la URL de conexión y úsala en `DATABASE_URL`

4. **Desplegar**
   - Click en "Deploy"
   - Coolify construirá y desplegará automáticamente:
     - Servicio Web (Django + Gunicorn)
     - Redis
     - Celery Worker
     - Celery Beat

### 3. Verificar el Despliegue

Una vez desplegado, verifica que todo funciona:

```bash
# Ver logs del servicio web
# En Coolify UI → Tu proyecto → Logs → web

# Ver logs del worker de Celery
# En Coolify UI → Tu proyecto → Logs → celery_worker

# Verificar que Redis está corriendo
# En Coolify UI → Tu proyecto → Logs → redis
```

### 4. Ejecutar Migraciones (Primera vez)

Si es el primer despliegue:

```bash
# Conectar al contenedor web en Coolify
# Coolify UI → Tu proyecto → web → Terminal

python manage.py migrate
python manage.py createsuperuser
```

## Arquitectura Desplegada

```
┌─────────────────────────────────────────┐
│           Coolify Server                │
├─────────────────────────────────────────┤
│                                         │
│  ┌──────────┐  ┌──────────┐           │
│  │   Web    │  │  Redis   │           │
│  │ (Django) │──│          │           │
│  └──────────┘  └──────────┘           │
│       │              │                 │
│       │         ┌────┴────┐           │
│       │         │         │           │
│  ┌────▼────┐  ┌▼────────▼┐           │
│  │ Celery  │  │  Celery  │           │
│  │ Worker  │  │   Beat   │           │
│  └─────────┘  └──────────┘           │
│                                         │
│  ┌─────────────────────────┐          │
│  │   PostgreSQL Database   │          │
│  └─────────────────────────┘          │
└─────────────────────────────────────────┘
```

## Recursos Utilizados

- **Web**: ~300-500MB RAM
- **Redis**: ~50-100MB RAM
- **Celery Worker**: ~200-300MB RAM
- **Celery Beat**: ~100-150MB RAM
- **Total**: ~650-1050MB RAM

## Escalamiento

Para escalar el worker de Celery:

1. En Coolify, ve a tu proyecto
2. Encuentra el servicio `celery_worker`
3. Ajusta el número de réplicas o la concurrencia

O modifica `docker-compose.yml`:
```yaml
celery_worker:
  # ...
  command: celery -A energia worker --loglevel=info --concurrency=4  # Aumentar concurrencia
  deploy:
    replicas: 2  # Múltiples workers
```

## Troubleshooting

### Worker no procesa tareas
```bash
# Verificar que Redis está accesible
docker exec -it <redis-container> redis-cli ping
# Debe responder: PONG

# Verificar logs del worker
# Coolify UI → Logs → celery_worker
```

### Errores de conexión a BD
```bash
# Verificar DATABASE_URL en variables de entorno
# Asegúrate de que el formato sea correcto:
# postgresql://usuario:contraseña@host:puerto/nombre_bd
```

### Importaciones no muestran progreso
```bash
# Verificar que el worker está corriendo
# Coolify UI → Services → celery_worker → Status: Running

# Verificar logs para errores
# Coolify UI → Logs → celery_worker
```

## Monitoreo (Opcional)

Para agregar Flower (dashboard de Celery):

1. Agrega a `docker-compose.yml`:
```yaml
  flower:
    build: .
    command: celery -A energia flower --port=5555
    ports:
      - "5555:5555"
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
    depends_on:
      - redis
```

2. Accede a `http://tu-dominio:5555`

## Mantenimiento

### Actualizar la aplicación
```bash
git push  # Coolify auto-desplegará si está configurado
```

### Limpiar tareas antiguas de Celery
```bash
# Conectar al contenedor web
python manage.py shell
>>> from django_celery_results.models import TaskResult
>>> TaskResult.objects.filter(date_done__lt='2024-01-01').delete()
```

### Backup de Redis (opcional)
Redis ya está configurado con persistencia (`appendonly yes`), pero puedes hacer backups manuales:
```bash
docker exec <redis-container> redis-cli BGSAVE
```

## Soporte

Si tienes problemas, revisa:
1. Logs en Coolify UI
2. Variables de entorno configuradas correctamente
3. Base de datos accesible
4. Redis corriendo y accesible
