document.addEventListener('DOMContentLoaded', function () {
    const confirmForm = document.querySelector('form[method="POST"]');
    // Buscamos el botón de confirmar importación
    const confirmBtn = document.querySelector('input[name="confirm"]');

    if (confirmForm && confirmBtn) {
        confirmForm.addEventListener('submit', function (e) {
            // Solo si se hizo click en confirmar
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
                <div class="progress-title">Procesando Importación...</div>
                <div class="progress-bar-bg">
                    <div id="import-progress-fill" class="progress-bar-fill" style="width: 0%"></div>
                </div>
                <div id="import-progress-text" class="progress-status">Preparando datos (0%)</div>
                <div class="progress-warning">Por favor, no cierre esta ventana hasta finalizar.</div>
            </div>
        `;
        document.body.appendChild(overlay);

        // Estilos premium inline para asegurar que se vea bien
        const style = document.createElement('style');
        style.textContent = `
            #import-progress-overlay {
                position: fixed;
                top: 0; left: 0; width: 100%; height: 100%;
                background: rgba(0, 0, 0, 0.85);
                backdrop-filter: blur(8px);
                z-index: 999999;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-family: 'Inter', system-ui, -apple-system, sans-serif;
            }
            .progress-container {
                width: 90%;
                max-width: 500px;
                background: #1e1e2e;
                padding: 40px;
                border-radius: 24px;
                box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
                text-align: center;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
            .progress-title {
                font-size: 24px;
                font-weight: 700;
                margin-bottom: 25px;
                background: linear-gradient(90deg, #ff4d4d, #ff9e9e);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }
            .progress-bar-bg {
                width: 100%;
                height: 14px;
                background: rgba(255, 255, 255, 0.05);
                border-radius: 10px;
                overflow: hidden;
                margin-bottom: 15px;
                border: 1px solid rgba(255, 255, 255, 0.05);
            }
            .progress-bar-fill {
                height: 100%;
                background: linear-gradient(90deg, #ff4d4d, #ff3333);
                box-shadow: 0 0 15px rgba(255, 77, 77, 0.5);
                transition: width 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            }
            .progress-status {
                font-size: 16px;
                color: #a0a0b8;
                margin-bottom: 10px;
            }
            .progress-warning {
                font-size: 12px;
                color: #6a6a8a;
                margin-top: 20px;
                font-style: italic;
            }
        `;
        document.head.appendChild(style);
    }

    function startPolling() {
        const fill = document.getElementById('import-progress-fill');
        const text = document.getElementById('import-progress-text');

        let consecutiveErrors = 0;

        const interval = setInterval(() => {
            fetch('/activos/api/get-import-progress/')
                .then(response => response.json())
                .then(data => {
                    consecutiveErrors = 0;
                    const percent = data.progress || 0;
                    if (fill) fill.style.width = percent + '%';
                    if (text) text.innerText = `Procesando... (${percent}%)`;

                    if (percent >= 100) {
                        text.innerText = "¡Guardando cambios finales!";
                    }
                })
                .catch(err => {
                    consecutiveErrors++;
                    if (consecutiveErrors > 10) {
                        clearInterval(interval);
                    }
                });
        }, 800);
    }
});
