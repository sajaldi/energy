@echo off
setlocal
cd /d "%~dp0"
call env\Scripts\activate.bat
if "%1"=="" (
    python abrir_ot.py --menu
) else (
    python abrir_ot.py %*
)
endlocal
