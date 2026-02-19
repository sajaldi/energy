# ============================================================
# Script para iniciar Django local con túnel SSH a la base de datos
# Uso: .\start_local.ps1
# ============================================================

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Energy - Inicio Local con Tunel SSH" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# --- Configuración del Túnel SSH ---
$SSH_USER     = "vboxuser"
$SSH_HOST     = "181.115.47.107"
$SSH_PORT     = 3456
$LOCAL_PORT   = 5433
$REMOTE_HOST  = "10.30.1.11"
$REMOTE_PORT  = 5432

# --- Verificar si el túnel ya está abierto ---
$existingTunnel = Get-NetTCPConnection -LocalPort $LOCAL_PORT -State Listen -ErrorAction SilentlyContinue

if ($existingTunnel) {
    Write-Host "[OK] Tunel SSH ya esta activo en el puerto $LOCAL_PORT" -ForegroundColor Green
} else {
    Write-Host "[...] Abriendo tunel SSH (puerto $LOCAL_PORT -> $REMOTE_HOST`:$REMOTE_PORT)..." -ForegroundColor Yellow
    
    # Abrir el túnel SSH en segundo plano
    $tunnelProcess = Start-Process -FilePath "ssh" `
        -ArgumentList "-p $SSH_PORT -L ${LOCAL_PORT}:${REMOTE_HOST}:${REMOTE_PORT} ${SSH_USER}@${SSH_HOST} -N -o StrictHostKeyChecking=no -o ServerAliveInterval=60 -o ServerAliveCountMax=3" `
        -PassThru -WindowStyle Minimized

    # Esperar un momento para que el túnel se establezca
    Start-Sleep -Seconds 3

    # Verificar si se abrió correctamente
    $tunnelCheck = Get-NetTCPConnection -LocalPort $LOCAL_PORT -State Listen -ErrorAction SilentlyContinue
    if ($tunnelCheck) {
        Write-Host "[OK] Tunel SSH establecido correctamente!" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] No se pudo abrir el tunel SSH." -ForegroundColor Red
        Write-Host "        Verifica que puedes conectar por SSH:" -ForegroundColor Red
        Write-Host "        ssh -p $SSH_PORT ${SSH_USER}@${SSH_HOST}" -ForegroundColor Yellow
        exit 1
    }
}

Write-Host ""
Write-Host "[...] Iniciando servidor Django..." -ForegroundColor Yellow
Write-Host ""

# --- Activar entorno virtual e iniciar Django ---
try {
    & "$PSScriptRoot\env\Scripts\Activate.ps1"
    python manage.py runserver
} finally {
    # Al cerrar Django (Ctrl+C), cerrar también el túnel
    if ($tunnelProcess -and !$tunnelProcess.HasExited) {
        Write-Host ""
        Write-Host "[...] Cerrando tunel SSH..." -ForegroundColor Yellow
        Stop-Process -Id $tunnelProcess.Id -Force -ErrorAction SilentlyContinue
        Write-Host "[OK] Tunel SSH cerrado." -ForegroundColor Green
    }
}
