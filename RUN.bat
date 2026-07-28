@echo off
setlocal
cd /d "%~dp0"

:: Configurar título de la ventana principal de control
title Gestor del Sistema - Energy

:: Limpiar pantalla y mostrar cabecera estilizada
cls
echo.
echo ======================================================================
echo   [SYSTEM LAUNCHER] - INICIANDO APLICACIONES DE ENERGIA
echo ======================================================================
echo.

:: --- PASO 1: ABRIR EL TUNEL ---
echo  [+] [1/2] Iniciando tunel de base de datos...
start "Softcom Tunnel" cmd /c "color 0A && title Softcom DB Tunnel && cd /d dist && echo [TUNEL] Ejecutando Softcom_DB_Tunnel.exe... && Softcom_DB_Tunnel.exe"
timeout /t 2 /nobreak >nul

:: --- PASO 2: ABRIR EL SERVIDOR PYTHON ---
echo  [+] [2/2] Levantando servidor Django (Python)...
start "Servidor Django" powershell -ExecutionPolicy Bypass -Command "$Host.UI.RawUI.WindowTitle = 'Servidor Django'; Write-Host '[DJANGO] Activando entorno virtual...' -ForegroundColor Cyan; & { .\env\Scripts\Activate.ps1; Write-Host '[DJANGO] Servidor listo. Ejecutando runserver...' -ForegroundColor Green; python manage.py runserver }"

echo.
echo ======================================================================
echo   [EXITO] Los procesos se estan ejecutando en ventanas separadas.
echo   Puedes cerrar esta ventana de control con total seguridad.
echo ======================================================================
echo.
pause