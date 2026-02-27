@echo off
REM Script para iniciar servicios de energia

echo ====================================
echo   Iniciando servicios de Energia
echo ====================================

REM Verificar si Redis esta corriendo
redis-cli ping >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Starting Redis...
    start "Redis" redis-server
    timeout /t 2 /nobreak >nul
)

REM Iniciar Celery Worker
start "Celery Worker" cmd /k "cd /d %~dp0 && call env\Scripts\python.exe -m celery -A energia worker -l info --concurrency=4"

REM Iniciar Flower (monitor web - opcional)
start "Celery Flower" cmd /k "cd /d %~dp0 && call env\Scripts\python.exe -m celery -A energia flower --port=5555"

echo.
echo Servicios iniciados:
echo - Redis: http://localhost:6379
echo - Celery Worker: Consola nueva
echo - Flower: http://localhost:5555
echo.
pause
