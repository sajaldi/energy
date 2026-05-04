@echo off
setlocal
title 🕒 ENERGIA - Celery Beat (LOCAL)
color 0E

echo.
echo  ==========================================================
echo     🕒 ENERGIA: SISTEMA DE GESTION DE ENERGIA
echo     Iniciando Celery Beat (Programador de Tareas)...
echo  ==========================================================
echo.

:: Verificar si existe el entorno virtual
if not exist "env\Scripts\python.exe" (
    color 0C
    echo [ERROR] No se encontro la carpeta 'env'. 
    pause
    exit /b
)

echo [+] Directorio: %~dp0
echo [+] App Celery: energia
echo.
echo ----------------------------------------------------------
echo  IMPORTANTE: Celery Beat solo envia las tareas. 
echo  Asegurate de tener un Worker ejecutandose tambien.
echo ----------------------------------------------------------
echo.

:: Iniciar Celery Beat
call env\Scripts\python.exe -m celery -A energia beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler

pause
