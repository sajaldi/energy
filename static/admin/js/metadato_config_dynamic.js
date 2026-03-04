(function($) {
    $(document).ready(function() {
        console.log("Metadato dynamic config JS loaded");

        function updateFields($modelSelect) {
            var $row = $modelSelect.closest('tr');
            var $fieldSelect = $row.find('select[id$="-campo_visualizacion"]');
            if (!$fieldSelect.length) return;
            
            var ctId = $modelSelect.val();
            
            if (ctId) {
                var currentVal = $fieldSelect.val();
                $fieldSelect.empty().append('<option value="">Cargando campos...</option>');
                
                $.getJSON('/documentos/api/model-fields/', { ct_id: ctId }, function(data) {
                    $fieldSelect.empty();
                    $fieldSelect.append('<option value="">---------</option>');
                    if (data.fields && data.fields.length > 0) {
                        $.each(data.fields, function(index, field) {
                            $fieldSelect.append($('<option>', {
                                value: field,
                                text: field
                            }));
                        });
                        if (currentVal && data.fields.indexOf(currentVal) !== -1) {
                            $fieldSelect.val(currentVal);
                        }
                    }
                }).fail(function() {
                    $fieldSelect.empty().append('<option value="">Error</option>');
                });
            } else {
                $fieldSelect.empty().append('<option value="">---------</option>');
            }
        }

        $(document).on('change', 'select[id^="id_metadatos_config-"][id$="-modelo_relativo"]', function() {
            updateFields($(this));
        });

        $(document).on('formset:added', function(event, $row, formsetName) {
            // El selector de 'formset:added' puede variar según la versión de Django/Jazzmin
            var $modelSelect = $row.find('select[id$="-modelo_relativo"]');
            if ($modelSelect.length) {
                updateFields($modelSelect);
            }
        });
    });
})(django.jQuery || jQuery);
