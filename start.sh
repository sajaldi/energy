#!/bin/bash
set -e

if [ "$SERVICE_TYPE" = "worker" ]; then
    echo "[WORKER] Iniciando Celery Worker..."
    exec celery -A energia worker --loglevel=info --concurrency=2 --max-tasks-per-child=50

elif [ "$SERVICE_TYPE" = "beat" ]; then
    echo "[BEAT] Iniciando Celery Beat..."
    exec celery -A energia beat --loglevel=info

else
    echo "[WEB] Aplicando migraciones..."
    python manage.py migrate --noinput

    echo "[WEB] Recolectando archivos estáticos..."
    python manage.py collectstatic --noinput --clear 2>/dev/null || \
    python manage.py collectstatic --noinput

    echo "[WEB] Iniciando Gunicorn..."
    exec gunicorn energia.wsgi:application \
        --bind 0.0.0.0:${PORT:-8000} \
        --workers ${GUNICORN_WORKERS:-3} \
        --threads ${GUNICORN_THREADS:-2} \
        --timeout ${GUNICORN_TIMEOUT:-120} \
        --keep-alive 5 \
        --max-requests 1000 \
        --max-requests-jitter 100 \
        --log-level info \
        --access-logfile - \
        --error-logfile -
fi
