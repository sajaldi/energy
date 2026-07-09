#!/bin/bash
# Deploy rápido — solo reconstruye si hay cambios reales
# Uso: ./deploy.sh [--full]
set -e

echo "═══════════════════════════════════════════"
echo " DEPLOY RÁPIDO — $(date '+%H:%M:%S')"
echo "═══════════════════════════════════════════"

START_TIME=$(date +%s)

# Detectar si requirements.txt cambió (necesita rebuild completo)
REQUIREMENTS_CHANGED=false
if [ "$1" = "--full" ]; then
    REQUIREMENTS_CHANGED=true
    echo "⚠  Forzando rebuild completo (--full)"
fi

# Pull últimos cambios
echo "📥 Pulling latest code..."
git pull --ff-only 2>/dev/null || git pull

if [ "$REQUIREMENTS_CHANGED" = true ]; then
    echo "📦 Requirements cambiaron — rebuild completo..."
    docker compose build --parallel
else
    echo "🚀 Solo código cambió — rebuild rápido..."
    # Solo reconstruye las capas que cambiaron (COPY . /app/)
    docker compose build --parallel --no-cache-filter=builder
fi

echo "🔄 Reiniciando servicios..."
# Rolling restart: web primero, luego workers
docker compose up -d --no-deps --remove-orphans web
sleep 2
docker compose up -d --no-deps celery_worker celery_beat

# Esperar a que web esté healthy
echo "⏳ Esperando health check..."
for i in $(seq 1 30); do
    if docker compose exec -T web curl -sf http://localhost:8000/admin/login/ > /dev/null 2>&1; then
        break
    fi
    sleep 1
done

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo ""
echo "═══════════════════════════════════════════"
echo " ✅ DEPLOY COMPLETADO en ${ELAPSED}s"
echo "═══════════════════════════════════════════"

# Mostrar estado
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
