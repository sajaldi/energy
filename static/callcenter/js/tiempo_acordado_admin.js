document.addEventListener('change', function(e) {
    if (e.target && e.target.id === 'id_enlace') {
        const enlaceId = e.target.value;
        if (!enlaceId) return;

        // AJAX to fetch Enlace details
        fetch(`/admin/callcenter/enlace/${enlaceId}/details/`)
            .then(res => res.json())
            .then(data => {
                if (data.institucion_id) {
                    const instSelect = document.getElementById('id_institucion');
                    if (instSelect) {
                        instSelect.value = data.institucion_id;
                        // Trigger change for Select2 if active
                        if (window.jQuery && jQuery(instSelect).data('select2')) {
                            jQuery(instSelect).trigger('change');
                        }
                    }
                }
                if (data.ubicacion_id) {
                    const ubiSelect = document.getElementById('id_ubicacion');
                    if (ubiSelect) {
                        ubiSelect.value = data.ubicacion_id;
                        // Trigger change for Select2 if active
                        if (window.jQuery && jQuery(ubiSelect).data('select2')) {
                            jQuery(ubiSelect).trigger('change');
                        }
                    }
                }
            })
            .catch(err => console.error('Error fetching enlace details:', err));
    }
});
