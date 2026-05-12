/**
 * Admin Search Hijacker - SoftCom CCG
 * Redirige la búsqueda del navbar a nuestra vista global unificada.
 */
(function() {
    function setupGlobalSearch() {
        const targetUrl = "/admin/global-search/";

        // Función para ejecutar la búsqueda global
        function doSearch(query) {
            if (query && query.trim()) {
                window.location.href = targetUrl + "?q=" + encodeURIComponent(query.trim());
                return true;
            }
            return false;
        }

        // 1. Interceptar el evento de envío del formulario (Enter)
        document.addEventListener('submit', function(e) {
            const form = e.target;
            const qInput = form.querySelector('input[name="q"]');
            
            // Solo actuar si es un input de búsqueda en el header/navbar
            if (qInput && (form.closest('.navbar') || form.closest('.main-header') || form.closest('.nav-sidebar'))) {
                e.preventDefault();
                e.stopPropagation();
                doSearch(qInput.value);
                return false;
            }
        }, true);

        // 2. Interceptar el click en el botón de búsqueda (Lupa)
        document.addEventListener('click', function(e) {
            const btn = e.target.closest('button');
            if (btn) {
                const form = btn.closest('form');
                if (form) {
                    const qInput = form.querySelector('input[name="q"]');
                    if (qInput && (form.closest('.navbar') || form.closest('.main-header'))) {
                        e.preventDefault();
                        e.stopPropagation();
                        doSearch(qInput.value);
                    }
                }
            }
        }, true);

        // 3. Función para "limpiar" visualmente el buscador de Jazzmin
        function polishSearchInputs() {
            const allSearchInputs = document.querySelectorAll('input[name="q"]');
            allSearchInputs.forEach(function(input) {
                const form = input.closest('form');
                if (!form || !(form.closest('.navbar') || form.closest('.main-header') || form.closest('.nav-sidebar'))) return;

                // Cambiar el placeholder para indicar que es GLOBAL
                input.placeholder = "Búsqueda Global...";
                input.title = "Buscar en todo el sistema";
                
                // Desactivar el autocompletado nativo de Jazzmin
                input.setAttribute('autocomplete', 'off');
                input.removeAttribute('data-typeahead');
                
                // Forzar visualmente la acción (por si acaso)
                form.action = targetUrl;

                // Quitar filtros ocultos
                form.querySelectorAll('input[type="hidden"]').forEach(function(hidden) {
                    if (hidden.name !== 'csrfmiddlewaretoken') {
                        hidden.remove();
                    }
                });
            });
        }

        // Ejecutar pulido inicial y observar cambios
        polishSearchInputs();
        const observer = new MutationObserver(polishSearchInputs);
        observer.observe(document.body, { childList: true, subtree: true });
        
        console.log("[SoftCom] Global Search interceptor ARMED.");
    }

    // Iniciar
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setupGlobalSearch);
    } else {
        setupGlobalSearch();
    }
})();
