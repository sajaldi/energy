/**
 * Ayuda Contextual Dinámica
 */
document.addEventListener('DOMContentLoaded', function() {
    const currentPath = window.location.pathname;
    
    if (currentPath.includes('/admin/')) {
        fetch(`/ayuda/api/check-context/?url=${encodeURIComponent(currentPath)}`)
            .then(response => response.json())
            .then(data => {
                if (data.help) {
                    injectHelpButton(data.help);
                }
            })
            .catch(err => console.error('Error cargando ayuda contextual:', err));
    }

    function injectHelpButton(help) {
        // Crear estilos dinámicos
        const style = document.createElement('style');
        style.innerHTML = `
            .context-help-btn { 
                position: fixed; bottom: 85px; right: 25px; z-index: 9999; 
                background: #3182ce; color: white !important; width: 50px; height: 50px; 
                border-radius: 50%; display: flex; align-items: center; justify-content: center; 
                box-shadow: 0 4px 12px rgba(49, 130, 206, 0.4); transition: all 0.3s; 
                text-decoration: none;
            }
            .context-help-btn:hover { transform: scale(1.1); background: #2b6cb0; }
            .help-tooltip {
                position: fixed; bottom: 95px; right: 85px; z-index: 9999;
                background: #2d3748; color: white; padding: 6px 12px; border-radius: 6px;
                font-size: 0.85rem; opacity: 0; transition: opacity 0.3s; pointer-events: none;
                white-space: nowrap;
            }
            .context-help-btn:hover + .help-tooltip { opacity: 1; }
        `;
        document.head.appendChild(style);

        // Crear botón e inyectar
        const btn = document.createElement('a');
        btn.href = help.url;
        btn.target = '_blank';
        btn.className = 'context-help-btn';
        btn.innerHTML = '<i class="fas fa-question" style="font-size: 1.2rem;"></i>';
        
        const tooltip = document.createElement('div');
        tooltip.className = 'help-tooltip';
        tooltip.innerText = `Ayuda: ${help.title}`;

        document.body.appendChild(btn);
        document.body.appendChild(tooltip);
    }
});
