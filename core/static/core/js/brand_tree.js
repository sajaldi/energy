document.addEventListener('DOMContentLoaded', function() {
    // Usamos delegación de eventos para manejar clics en las marcas
    document.querySelector('#result_list').addEventListener('click', function(e) {
        const node = e.target.closest('.brand-tree-node');
        if (!node) return;

        // PREVENIR la navegación por defecto de Django Admin
        e.preventDefault();
        e.stopPropagation();

        const brandId = node.dataset.brandId;
        const row = node.closest('tr');
        const icon = node.querySelector('.tree-toggle i');
        
        // Verificar si ya existe la fila de detalles
        let detailRow = document.getElementById('details-' + brandId);

        if (detailRow) {
            // Alternar visibilidad si ya existe
            if (detailRow.style.display === 'none') {
                detailRow.style.display = 'table-row';
                icon.classList.remove('fa-chevron-right');
                icon.classList.add('fa-chevron-down');
            } else {
                detailRow.style.display = 'none';
                icon.classList.remove('fa-chevron-down');
                icon.classList.add('fa-chevron-right');
            }
        } else {
            // Cargar datos por AJAX
            icon.classList.remove('fa-chevron-right');
            icon.classList.add('fa-spinner', 'fa-spin');
            
            const url = brandId + '/get_models_ajax/';
            
            fetch(url)
                .then(response => response.text())
                .then(html => {
                    // Crear nueva fila
                    detailRow = document.createElement('tr');
                    detailRow.id = 'details-' + brandId;
                    detailRow.className = 'detail-row';
                    
                    // Colspan generoso para cubrir todas las columnas del admin
                    const cell = document.createElement('td');
                    cell.colSpan = 10; 
                    cell.innerHTML = html;
                    detailRow.appendChild(cell);
                    
                    // Insertar después de la fila actual
                    row.parentNode.insertBefore(detailRow, row.nextSibling);
                    
                    // Cambiar icono
                    icon.classList.remove('fa-spinner', 'fa-spin');
                    icon.classList.add('fa-chevron-down');
                })
                .catch(error => {
                    console.error('Error cargando modelos:', error);
                    icon.classList.remove('fa-spinner', 'fa-spin');
                    icon.classList.add('fa-exclamation-triangle', 'text-danger');
                });
        }
    });
});
