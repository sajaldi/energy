(function () {
    function initFilter() {
        const $ = window.django ? django.jQuery : window.jQuery;
        if (!$) return;

        function updateSubDisciplinas(disId) {
            const $sub = $('#id_sub_disciplina');
            const $rutina = $('#id_rutina');

            // Limpiar y disparar cambio para Select2
            $sub.empty().append('<option value="">---------</option>').trigger('change');
            $rutina.empty().append('<option value="">---------</option>').trigger('change');

            if (!disId) return;

            $.getJSON('/mantenimiento/ajax/get-subdisciplinas/', { disciplina_id: disId }, function (data) {
                $.each(data, function (i, item) {
                    $sub.append(new Option(item.nombre, item.id));
                });
                // Importante: Disparar cambio para que Select2 se entere de los nuevos options
                $sub.trigger('change');
            });
        }

        function updateRutinas(subId) {
            const $rutina = $('#id_rutina');
            $rutina.empty().append('<option value="">---------</option>').trigger('change');

            if (!subId) return;

            $.getJSON('/mantenimiento/ajax/get-rutinas/', { subdisciplina_id: subId }, function (data) {
                $.each(data, function (i, item) {
                    $rutina.append(new Option(item.nombre, item.id));
                });
                $rutina.trigger('change');
            });
        }

        // Usar delegación en el documento para asegurar que capturamos los eventos de los selects
        // Incluso si son reinicializados por Select2
        $(document).on('change', '#id_disciplina', function () {
            updateSubDisciplinas($(this).val());
        });

        $(document).on('change', '#id_sub_disciplina', function () {
            updateRutinas($(this).val());
        });
    }

    // En el admin de Django, django.jQuery suele estar disponible globalmente
    // Pero nos aseguramos de que el DOM esté listo
    if (document.readyState === 'complete' || document.readyState === 'interactive') {
        initFilter();
    } else {
        document.addEventListener('DOMContentLoaded', initFilter);
    }
})();
