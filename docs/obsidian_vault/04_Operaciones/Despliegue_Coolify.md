# 🚀 Especificaciones de Despliegue en Coolify / Docker

El ecosistema **Energy** se despliega de manera automatizada utilizando **Coolify**, permitiendo despliegues continuos y controlados con Docker.

## 🏗️ Dockerfile del Ecosistema
El despliegue utiliza una imagen base oficial de Python. Los servicios web y workers comparten la misma imagen Docker, ejecutando diferentes comandos según la configuración de Coolify.

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    python3-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Comando por defecto para el web server
CMD ["gunicorn", "energia.wsgi:application", "--bind", "0.0.0.0:8000"]
```

## 📋 Configuración en Coolify

En el dashboard de Coolify, el ecosistema se configura mediante un archivo `docker-compose.yml` multi-contenedor:

1. **`web`**: Servicio Django que sirve las solicitudes HTTP mediante Gunicorn en el puerto `8000`.
2. **`worker`**: Worker de Celery para tareas asíncronas pesadas (se ejecuta sin mapear puertos, con comando `celery -A energia worker -l info`).
3. **`beat`**: Planificador Celery Beat para rutinas periódicas de mantenimiento.
4. **`redis`**: Contenedor oficial de Redis como Broker de mensajería rápido.
5. **`postgres`**: Contenedor de PostgreSQL para la base de datos persistente.
6. **`minio`**: Object Storage para almacenamiento de archivos PDFs y planos.

## 🛡️ Variables de Entorno en Producción (Configuradas en Coolify)
- `DEBUG=False`
- `SECRET_KEY=<clave_segura_produccion>`
- `DATABASE_URL=postgres://user:password@postgres:5432/dbname`
- `CELERY_BROKER_URL=redis://redis:6379/0`
- `AWS_ACCESS_KEY_ID=<minio_user>`
- `AWS_SECRET_ACCESS_KEY=<minio_password>`
- `AWS_STORAGE_BUCKET_NAME=energy-docs`
- `AWS_S3_ENDPOINT_URL=http://minio:9000`

---
🔙 Volver a [[00_Inicio|Inicio]]
