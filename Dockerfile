# Dockerfile optimizado para Django + Celery en Coolify

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# 1. Instalar dependencias del sistema base
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    postgresql-client \
    pkg-config \
    libcairo2-dev \
    python3-dev \
    libreoffice-writer \
    fonts-liberation \
    default-jre \
    && rm -rf /var/lib/apt/lists/*

# 2. Instalación de dependencias de Python (Capa con caché persistente)
COPY requirements.txt /app/
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 3. Playwright (Instalación separada para caché)
# Instalamos Chromium y sus dependencias de sistema específicas
RUN playwright install --with-deps chromium

# 4. Copiar código de la aplicación (Capa que cambia frecuentemente)
COPY . /app/

# 5. Preparación de entorno
RUN mkdir -p /app/media /app/staticfiles
RUN python manage.py collectstatic --noinput || true

# Configuración de ejecución
EXPOSE 8000
RUN chmod +x /app/start.sh

# El comando se define por el script de inicio (Web por defecto)
CMD ["/bin/bash", "/app/start.sh"]
