/**
 * Admin Search Hijacker - SoftCom CCG
 * Redirige la búsqueda del navbar a nuestra vista global unificada.
 */
document.addEventListener('DOMContentLoaded', function () {
    // Jazzmin suele usar una estructura específica en el navbar para la búsqueda
    // Intentamos capturar el formulario tanto por clase como por el input name 'q'
    const searchInput = document.querySelector('.navbar-search input[name="q"], .nav-sidebar input[name="q"]');
    const searchForm = searchInput ? searchInput.closest('form') : null;

    if (searchForm) {
        searchForm.addEventListener('submit', function (e) {
            // Evitamos el comportamiento por defecto de redirección a un modelo específico
            e.preventDefault();

            const query = searchInput.value.trim();
            if (query) {
                // Redirigir a nuestra vista global unificada
                window.location.href = `/admin/global-search/?q=${encodeURIComponent(query)}`;
            }
        });

        // También manejamos el clic en el botón de la lupa si existe
        const searchButton = searchForm.querySelector('button[type="submit"]');
        if (searchButton) {
            searchButton.addEventListener('click', function (e) {
                // El evento submit del form se disparará y el listener anterior lo manejará
            });
        }
    }

    // DEBUG: Log para confirmar carga en entorno de desarrollo
    console.log("Global Search hijacker initialized.");
});
