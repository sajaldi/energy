@echo off
REM Script para iniciar servicios de energia

title Energia Celery Worker
echo Starting Celery Worker...
cd /d %~dp0
call env\Scripts\python.exe -m celery -A energia worker -l info --concurrency=4
