/**
 * Admin Search Hijacker - SoftCom CCG
 * Redirige la búsqueda del navbar a nuestra vista global unificada.
 */
document.addEventListener('DOMContentLoaded', function () {
    // Buscar TODOS los inputs con name="q" en la página
    // Esto cubre cualquier versión de Jazzmin o AdminLTE
    const allSearchInputs = document.querySelectorAll('input[name="q"]');

    allSearchInputs.forEach(function(searchInput) {
        const searchForm = searchInput.closest('form');
        if (!searchForm) return;

        // Sólo interceptar si el form NO es el de la lista de cambios de Django admin
        // (esos tienen action que apunta a una URL específica del modelo, no la global)
        // Regla: si el input está en el header/navbar (no en #content), lo interceptamos
        const inContent = searchInput.closest('#content, .content-wrapper > .content');
        if (inContent) return; // Dejar pasar el buscador inline de la lista de objetos

        // Modificar la acción del formulario directamente
        searchForm.action = "/admin/global-search/";
        searchForm.method = "GET";

        // Cambiar el placeholder
        searchInput.placeholder = "Buscador Global...";

        // Limpiar inputs ocultos que Jazzmin/AdminLTE puedan haberle agregado
        searchForm.querySelectorAll('input[type="hidden"]').forEach(function(hidden) {
            hidden.remove();
        });

        // Asegurar nombre correcto del campo
        searchInput.name = "q";
    });

    console.log("[SoftCom] Global Search hijacker loaded. Inputs intercepted:", allSearchInputs.length);
});
