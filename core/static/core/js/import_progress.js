/**
 * Módulo de Progreso de Importación - Versión Optimizada
 * Muestra seguimiento en tiempo real con información detallada
 */
document.addEventListener('DOMContentLoaded', function () {
    const confirmForm = document.querySelector('form[method="POST"]');
    const confirmBtn = document.querySelector('input[name="confirm"]');

    if (confirmForm && confirmBtn) {
        confirmForm.addEventListener('submit', function (e) {
            if (document.activeElement === confirmBtn) {
                showProgressOverlay();
                startPolling();
            }
        });
    }

    function showProgressOverlay() {
        const overlay = document.createElement('div');
        overlay.id = 'import-progress-overlay';
        overlay.innerHTML = `
            <div class="progress-container">
                <div class="progress-header">
                    <div class="progress-icon">⚡</div>
                    <div class="progress-title">Importando Activos</div>
                </div>
                
                <div class="progress-bar-bg">
                    <div id="import-progress-fill" class="progress-bar-fill" style="width: 0%"></div>
                </div>
                
                <div class="progress-info">
                    <div id="import-progress-percent" class="progress-percent">0%</div>
                    <div id="import-progress-speed" class="progress-speed">-- items/s</div>
                </div>
                
                <div id="import-current-item" class="current-item">Preparando datos...</div>
                
                <div class="stats-grid">
                    <div class="stat-box stat-new">
                        <div class="stat-icon">✨</div>
                        <div class="stat-value" id="stat-new">0</div>
                        <div class="stat-label">Nuevos</div>
                    </div>
                    <div class="stat-box stat-update">
                        <div class="stat-icon">🔄</div>
                        <div class="stat-value" id="stat-update">0</div>
                        <div class="stat-label">Actualizados</div>
                    </div>
                    <div class="stat-box stat-skip">
                        <div class="stat-icon">⏭️</div>
                        <div class="stat-value" id="stat-skip">0</div>
                        <div class="stat-label">Omitidos</div>
                    </div>
                    <div class="stat-box stat-error">
                        <div class="stat-icon">⚠️</div>
                        <div class="stat-value" id="stat-error">0</div>
                        <div class="stat-label">Errores</div>
                    </div>
                </div>
                
                <div id="import-processed" class="processed-count">Procesados: 0</div>
                
                <div class="progress-warning">
                    <span class="warning-icon">🔒</span>
                    No cierre esta ventana hasta que finalice la importación
                </div>
            </div>
        `;
        document.body.appendChild(overlay);

        const style = document.createElement('style');
        style.textContent = `
            #import-progress-overlay {
                position: fixed;
                top: 0; left: 0; width: 100%; height: 100%;
                background: rgba(10, 10, 20, 0.95);
                backdrop-filter: blur(12px);
                z-index: 999999;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
            }
            .progress-container {
                width: 90%;
                max-width: 520px;
                background: linear-gradient(145deg, #1a1a2e, #16213e);
                padding: 35px 40px;
                border-radius: 24px;
                box-shadow: 0 25px 60px -15px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(255,255,255,0.05);
                text-align: center;
            }
            .progress-header {
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 12px;
                margin-bottom: 28px;
            }
            .progress-icon {
                font-size: 28px;
                animation: pulse 1.5s ease-in-out infinite;
            }
            @keyframes pulse {
                0%, 100% { transform: scale(1); opacity: 1; }
                50% { transform: scale(1.15); opacity: 0.8; }
            }
            .progress-title {
                font-size: 22px;
                font-weight: 700;
                background: linear-gradient(90deg, #00d4ff, #00ff88);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }
            .progress-bar-bg {
                width: 100%;
                height: 16px;
                background: rgba(255, 255, 255, 0.08);
                border-radius: 10px;
                overflow: hidden;
                margin-bottom: 12px;
                border: 1px solid rgba(255,255,255,0.05);
            }
            .progress-bar-fill {
                height: 100%;
                background: linear-gradient(90deg, #00d4ff, #00ff88);
                box-shadow: 0 0 20px rgba(0, 212, 255, 0.4);
                transition: width 0.3s ease-out;
                border-radius: 10px;
            }
            .progress-info {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 20px;
                padding: 0 5px;
            }
            .progress-percent {
                font-size: 32px;
                font-weight: 800;
                color: #00d4ff;
            }
            .progress-speed {
                font-size: 14px;
                color: #00ff88;
                font-weight: 600;
                background: rgba(0,255,136,0.1);
                padding: 6px 14px;
                border-radius: 20px;
                border: 1px solid rgba(0,255,136,0.2);
            }
            .current-item {
                font-size: 14px;
                color: #a0a0c0;
                margin-bottom: 24px;
                padding: 12px 16px;
                background: rgba(255,255,255,0.03);
                border-radius: 10px;
                border: 1px solid rgba(255,255,255,0.05);
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }
            .current-item::before {
                content: '📌 ';
            }
            .stats-grid {
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 10px;
                margin-bottom: 20px;
            }
            .stat-box {
                background: rgba(255,255,255,0.03);
                padding: 14px 8px;
                border-radius: 12px;
                border: 1px solid rgba(255,255,255,0.05);
                transition: transform 0.2s, box-shadow 0.2s;
            }
            .stat-box:hover {
                transform: translateY(-2px);
                box-shadow: 0 8px 20px rgba(0,0,0,0.3);
            }
            .stat-icon {
                font-size: 18px;
                margin-bottom: 6px;
            }
            .stat-value {
                font-size: 22px;
                font-weight: 800;
                margin-bottom: 2px;
            }
            .stat-label {
                font-size: 10px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                opacity: 0.6;
            }
            .stat-new .stat-value { color: #00ff88; }
            .stat-update .stat-value { color: #00d4ff; }
            .stat-skip .stat-value { color: #ffd700; }
            .stat-error .stat-value { color: #ff4d4d; }
            .processed-count {
                font-size: 13px;
                color: #6a6a8a;
                margin-bottom: 20px;
            }
            .progress-warning {
                font-size: 12px;
                color: #5a5a7a;
                padding: 12px;
                background: rgba(255,77,77,0.05);
                border-radius: 8px;
                border: 1px solid rgba(255,77,77,0.1);
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
            }
            .warning-icon {
                font-size: 14px;
            }
        `;
        document.head.appendChild(style);
    }

    function startPolling() {
        const fill = document.getElementById('import-progress-fill');
        const percentText = document.getElementById('import-progress-percent');
        const speedText = document.getElementById('import-progress-speed');
        const currentItem = document.getElementById('import-current-item');
        const processedText = document.getElementById('import-processed');
        const statNew = document.getElementById('stat-new');
        const statUpdate = document.getElementById('stat-update');
        const statSkip = document.getElementById('stat-skip');
        const statError = document.getElementById('stat-error');

        let consecutiveErrors = 0;
        let lastProcessed = 0;

        const interval = setInterval(() => {
            fetch('/activos/api/get-import-progress/')
                .then(response => response.json())
                .then(data => {
                    consecutiveErrors = 0;

                    const percent = data.progress || 0;
                    if (fill) fill.style.width = percent + '%';
                    if (percentText) percentText.innerText = percent + '%';

                    if (speedText && data.speed !== undefined) {
                        speedText.innerText = data.speed + ' items/s';
                    }

                    if (currentItem && data.current_item) {
                        currentItem.innerText = data.current_item;
                    }

                    if (processedText && data.processed !== undefined) {
                        processedText.innerText = `Procesados: ${data.processed}`;
                        lastProcessed = data.processed;
                    }

                    if (data.stats) {
                        if (statNew) statNew.innerText = data.stats.new || 0;
                        if (statUpdate) statUpdate.innerText = data.stats.update || 0;
                        if (statSkip) statSkip.innerText = data.stats.skip || 0;
                        if (statError) statError.innerText = data.stats.error || 0;
                    }

                    if (percent >= 100) {
                        if (currentItem) currentItem.innerText = '¡Guardando cambios finales!';
                        if (percentText) percentText.innerText = '100%';
                    }
                })
                .catch(err => {
                    consecutiveErrors++;
                    if (consecutiveErrors > 15) {
                        clearInterval(interval);
                    }
                });
        }, 500);  // Polling más frecuente para mayor fluidez
    }
});
