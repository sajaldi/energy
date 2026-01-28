#!/bin/bash

# Salir si hay errores
set -e

if [ "$SERVICE_TYPE" = "worker" ]; then
    echo "🚀 Iniciando Celery Worker..."
    celery -A energia worker --loglevel=info
else
    echo "🌐 Iniciando Django Web Server..."
    python manage.py migrate
    gunicorn energia.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 3 --timeout 300
fi
