/**
 * Admin Search Hijacker - SoftCom CCG
 * Redirige la búsqueda del navbar a nuestra vista global unificada.
 */
document.addEventListener('DOMContentLoaded', function () {
    function hijack() {
        // Buscar inputs con nombre 'q' (estándar de Django admin y Jazzmin)
        const allSearchInputs = document.querySelectorAll('input[name="q"]');

        allSearchInputs.forEach(function(searchInput) {
            const searchForm = searchInput.closest('form');
            if (!searchForm) return;

            // Sólo interceptar si el input está en el header/navbar (no en el listado de objetos)
            const inHeader = searchInput.closest('.main-header, .navbar, #jazmin-navbar, .nav-sidebar');
            if (!inHeader) return; 

            // Redirigir a nuestra vista unificada
            if (!searchForm.action.includes('/admin/global-search/')) {
                searchForm.action = "/admin/global-search/";
                searchForm.method = "GET";
            }

            // Mejorar placeholder para que sea claro que es GLOBAL
            searchInput.placeholder = "Búsqueda Global (Equipos, Tickets, Usuarios...)";
            searchInput.title = "Buscar en todo el sistema";
            
            // Si hay un label cerca (ej. en el sidebar), actualizarlo
            const label = searchForm.querySelector('label') || searchForm.previousElementSibling;
            if (label && label.tagName === 'LABEL') {
                label.innerText = "Buscador Global";
            }

            // Limpiar filtros ocultos de Jazzmin que forzarían la búsqueda a un solo modelo
            searchForm.querySelectorAll('input[type="hidden"]').forEach(function(hidden) {
                hidden.remove();
            });

            // Asegurar que el nombre del parámetro sea 'q'
            searchInput.name = "q";
        });
    }

    // Ejecutar al cargar
    hijack();

    // Observar cambios en el DOM por si Jazzmin renderiza elementos dinámicamente
    const observer = new MutationObserver((mutations) => {
        hijack();
    });
    observer.observe(document.body, { childList: true, subtree: true });

    console.log("[SoftCom] Global Search hijacker active.");
});
