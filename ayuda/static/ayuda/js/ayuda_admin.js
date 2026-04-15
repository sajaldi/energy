document.addEventListener('DOMContentLoaded', function() {
    // Buscar el campo de contenido (textarea)
    var contentField = document.querySelector('#id_contenido');
    
    if (contentField) {
        // Inicializar SimpleMDE
        var simplemde = new SimpleMDE({ 
            element: contentField,
            spellChecker: false,
            autosave: {
                enabled: true,
                uniqueId: "ayuda_articulo_" + (window.location.pathname.split('/')[4] || 'new'),
                delay: 1000,
            },
            toolbar: [
                "bold", "italic", "heading", "|", 
                "quote", "unordered-list", "ordered-list", "|", 
                "link", "image", "table", "|", 
                "preview", "side-by-side", "fullscreen", "|", 
                "guide"
            ],
            placeholder: "Escriba el contenido del artículo aquí usando Markdown...",
            status: ["autosave", "lines", "words", "cursor"],
        });

        // Asegurar que SimpleMDE guarde el contenido antes de enviar el formulario
        contentField.closest('form').addEventListener('submit', function() {
            contentField.value = simplemde.value();
        });

        // --- Lógica de PEGADO de imágenes (Ctrl+V) ---
        var codemirror = simplemde.codemirror;
        
        codemirror.on('paste', function(cm, e) {
            var items = (e.clipboardData || e.originalEvent.clipboardData).items;
            for (var index in items) {
                var item = items[index];
                if (item.kind === 'file' && item.type.includes('image')) {
                    var blob = item.getAsFile();
                    
                    // Prevenir comportamiento por defecto
                    e.preventDefault();
                    
                    // Insertar marcador de carga
                    var pos = cm.getCursor();
                    var placeholder = "![Subiendo imagen...]()";
                    cm.replaceRange(placeholder, pos);
                    
                    // Subir archivo al servidor
                    uploadImage(blob, function(url) {
                        // Reemplazar marcador con el link final
                        var content = cm.getValue();
                        var newContent = content.replace(placeholder, "![Imagen](" + url + ")");
                        cm.setValue(newContent);
                        // Reposicionar cursor al final del link
                        cm.setCursor({line: pos.line, ch: pos.ch + url.length + 10});
                    }, function(error) {
                        alert("Error al subir imagen: " + error);
                        var content = cm.getValue();
                        cm.setValue(content.replace(placeholder, ""));
                    });
                }
            }
        });
    }

    // Función auxiliar para subir imagen via AJAX
    function uploadImage(file, successCallback, errorCallback) {
        var formData = new FormData();
        formData.append('image', file);
        
        // Obtener CRSF Token
        var csrftoken = getCookie('csrftoken');

        fetch('/ayuda/admin/upload-image/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrftoken
            },
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                successCallback(data.url);
            } else {
                errorCallback(data.message);
            }
        })
        .catch(error => errorCallback(error));
    }

    // Helper para obtener cookies
    function getCookie(name) {
        var cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            var cookies = document.cookie.split(';');
            for (var i = 0; i < cookies.length; i++) {
                var cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
});
