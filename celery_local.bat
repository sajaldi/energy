@echo off
setlocal
title 🚀 ENERGIA - Celery Worker (LOCAL)
color 0B

echo.
echo  ==========================================================
echo     🚀 ENERGIA: SISTEMA DE GESTION DE ENERGIA
echo     Iniciando Celery Worker en entorno LOCAL...
echo  ==========================================================
echo.

:: Verificar si existe el entorno virtual
if not exist "env\Scripts\python.exe" (
    color 0C
    echo [ERROR] No se encontro la carpeta 'env'. 
    echo Por favor, asegurese de que el entorno virtual este en la carpeta 'env'.
    pause
    exit /b
)

:: Mostrar información de inicio
echo [+] Directorio: %~dp0
echo [+] Entorno: Local
echo [+] App Celery: energia
echo [+] Pool: solo (Modo compatible para Windows)
echo.
echo ----------------------------------------------------------
echo  CONSEJO: Para mejor rendimiento en Windows, puedes instalar
echo  eventlet (pip install eventlet) y cambiar '-P solo' por 
echo  '-P eventlet' en este archivo.
echo ----------------------------------------------------------
echo.

:: Iniciar Celery Worker
:: Usamos -P solo porque es el modo mas estable en Windows sin dependencias extra
call env\Scripts\python.exe -m celery -A energia worker -l info -P solo

pause
