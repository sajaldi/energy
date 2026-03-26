@echo off
title Monitor de Vectorización de Tickets
color 0A
chcp 65001 >nul

:loop
cls
echo.
echo  ╔══════════════════════════════════════════════════════════════╗
echo  ║         MONITOR DE VECTORIZACIÓN DE TICKETS                 ║
echo  ╚══════════════════════════════════════════════════════════════╝
echo.

cd /d d:\Apps\energia\energy
env\Scripts\python.exe -c "
import os, sys, datetime
os.environ['DJANGO_SETTINGS_MODULE']='energia.settings'

# 1. Verificar Ollama
ollama_ok = False
ollama_models = []
try:
    import requests
    r = requests.get('http://localhost:11434/api/tags', timeout=3)
    if r.status_code == 200:
        ollama_ok = True
        data = r.json()
        ollama_models = [m['name'] for m in data.get('models', [])]
except:
    pass

print('  ── ESTADO DE OLLAMA ──')
if ollama_ok:
    print(f'  🟢 Ollama: ACTIVO (localhost:11434)')
    if ollama_models:
        print(f'  📦 Modelos: {', '.join(ollama_models)}')
    has_embed = any('mxbai' in m for m in ollama_models)
    if not has_embed:
        print(f'  ⚠️  ADVERTENCIA: mxbai-embed-large NO encontrado!')
        print(f'     Ejecuta: ollama pull mxbai-embed-large')
else:
    print(f'  🔴 Ollama: NO RESPONDE')
    print(f'     Verifica que Ollama esté corriendo.')

# 2. Verificar Celery
print()
print('  ── ESTADO DE CELERY ──')
celery_ok = False
try:
    from django.core.cache import cache
    # Intentar verificar si hay tareas activas via Redis
    import redis
    r_client = redis.from_url('redis://default:saul123@localhost:6379/1', socket_connect_timeout=2)
    r_client.ping()
    # Revisar si hay tareas pendientes en la cola
    pending = r_client.llen('celery')
    print(f'  🟢 Redis: CONECTADO')
    print(f'  📬 Tareas en cola: {pending}')
    celery_ok = True
except Exception as e:
    print(f'  🔴 Redis: NO DISPONIBLE ({str(e)[:40]})')

# 3. Progreso de vectorización
print()
print('  ── PROGRESO DE VECTORIZACIÓN ──')
import django; django.setup()
from callcenter.models import SolicitudTicket

total = SolicitudTicket.objects.count()
con = SolicitudTicket.objects.exclude(embedding__isnull=True).count()
sin = total - con
pct = con * 100 // total if total else 0

llenos = pct // 2
vacios = 50 - llenos
barra = '█' * llenos + '░' * vacios

ahora = datetime.datetime.now().strftime('%%H:%%M:%%S')

print(f'  Hora: {ahora}')
print()
print(f'  [{barra}] {pct}%%')
print()
print(f'  ✅ Con vector:  {con:,}')
print(f'  ❌ Sin vector:  {sin:,}')
print(f'  📊 Total:       {total:,}')
print()
if sin == 0:
    print(f'  🎉 ¡COMPLETADO! Todos los tickets están vectorizados.')
elif not ollama_ok:
    print(f'  ⛔ DETENIDO: Ollama no está corriendo. Inícialo primero.')
else:
    vel = con / max(1, 1)  # placeholder
    print(f'  ⏳ Procesando... {sin:,} tickets pendientes.')
"

echo.
echo  ─────────────────────────────────────────────────────────────
echo   Actualizando en 10 segundos... (Ctrl+C para salir)
timeout /t 10 /nobreak >nul
goto loop
