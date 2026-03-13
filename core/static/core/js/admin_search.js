/**
 * Admin Search Hijacker - SoftCom CCG
 * Redirige la búsqueda del navbar a nuestra vista global unificada.
 */
document.addEventListener('DOMContentLoaded', function () {
    // Jazzmin suele usar una estructura específica en el navbar para la búsqueda
    // Intentamos capturar cualquier input de búsqueda (name="q") que esté en el navbar superior
    const searchInputs = document.querySelectorAll('.navbar input[name="q"], .navbar-search input[name="q"], .nav-sidebar input[name="q"]');
    
    searchInputs.forEach(searchInput => {
        const searchForm = searchInput.closest('form');

        if (searchForm) {
            // Modificar la acción del formulario directamente para asegurar la redirección nativa
            searchForm.action = "/admin/global-search/";
            searchForm.method = "GET";

            // Personalizar el placeholder para indicar búsqueda global
            searchInput.placeholder = "Buscador Global (Apps, Modelos, Códigos, Contenido)...";
            searchInput.style.width = "400px"; // Opcional: Hacerlo un poco más ancho
            searchInput.style.transition = "width 0.3s";

            // Eliminar parámetros ocultos que Jazzmin podría agregar (si los hay)
            const hiddenInputs = searchForm.querySelectorAll('input[type="hidden"]');
            hiddenInputs.forEach(input => input.remove());
        }
    });

    // DEBUG: Log para confirmar carga en entorno de desarrollo
    console.log("Global Search hijacker initialized.");
});
