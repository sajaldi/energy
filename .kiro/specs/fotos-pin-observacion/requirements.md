# Requirements Document

## Introduction

Esta funcionalidad agrega la capacidad de adjuntar fotografías a los pines de observación en los planos PDF de proyecto. Los usuarios podrán subir fotos tanto durante la creación de un pin como después desde el modal de detalle, visualizarlas como grilla de miniaturas, ampliarlas en un lightbox, y eliminarlas individualmente. Las imágenes se comprimen automáticamente siguiendo el patrón existente de `compress_image` del módulo `core.image_utils`.

## Glossary

- **Sistema**: La aplicación web Django del módulo de proyectos (`proyectos` app)
- **FotoPinObservacion**: Modelo que almacena una foto adjunta a un PinObservacionProyecto
- **PinObservacionProyecto**: Modelo existente que vincula una observación a una posición en un plano PDF de proyecto
- **Visor**: La vista `visor_plano_proyecto` que renderiza el plano PDF con pines interactivos
- **Modal_Detalle**: El modal existente que muestra información del pin al hacer clic izquierdo sobre un pin
- **Modal_Creación**: El modal existente que permite crear un nuevo pin de observación
- **Lightbox**: Componente de visualización a pantalla completa para ver fotos en tamaño original
- **Grilla_Miniaturas**: Componente de visualización de fotos en formato de cuadrícula dentro del Modal_Detalle
- **compress_image**: Función existente en `core.image_utils` que redimensiona y comprime imágenes a JPEG

## Requirements

### Requirement 1: Modelo de datos para fotos de pin

**User Story:** Como desarrollador, quiero un modelo que almacene fotos asociadas a un pin de observación, para que cada pin pueda tener evidencia fotográfica adjunta.

#### Acceptance Criteria

1.1 THE Sistema SHALL almacenar cada foto de pin con una referencia FK al PinObservacionProyecto, un campo ImageField para la imagen, y un campo DateTimeField de fecha de creación.

1.2 THE Sistema SHALL almacenar las imágenes en la ruta `proyectos/fotos_pines/` dentro del almacenamiento configurado.

1.3 WHEN se guarda una FotoPinObservacion, THE Sistema SHALL comprimir la imagen usando la función `compress_image` con los parámetros por defecto (max_width=1024, quality=70).

1.4 WHEN se elimina un PinObservacionProyecto, THE Sistema SHALL eliminar en cascada todas las FotoPinObservacion asociadas a ese pin.

1.5 THE Sistema SHALL limitar a un máximo de 5 fotos por PinObservacionProyecto.

### Requirement 2: Subida de fotos durante la creación del pin

**User Story:** Como usuario staff, quiero poder adjuntar fotos al momento de crear un pin de observación, para registrar evidencia visual desde el primer instante.

#### Acceptance Criteria

2.1 WHILE el Modal_Creación está visible, THE Sistema SHALL mostrar un campo de carga de archivos que permita seleccionar hasta 5 imágenes.

2.2 THE Sistema SHALL aceptar archivos en formato JPG y PNG para la carga de fotos.

2.3 WHEN el usuario selecciona archivos que no son JPG ni PNG, THE Sistema SHALL rechazar esos archivos y mostrar un mensaje de error indicando los formatos válidos.

2.4 WHEN el usuario intenta seleccionar más de 5 fotos en total, THE Sistema SHALL impedir la selección y mostrar un mensaje indicando el límite máximo de 5 fotos.

2.5 WHEN el usuario guarda el pin con fotos adjuntas, THE Sistema SHALL enviar las fotos al servidor junto con los datos del pin mediante una solicitud AJAX multipart.

2.6 IF la subida de fotos falla durante la creación del pin, THEN THE Sistema SHALL crear el pin sin fotos y mostrar un mensaje informando que las fotos no se pudieron subir.

### Requirement 3: Subida de fotos desde el modal de detalle

**User Story:** Como usuario staff, quiero poder agregar fotos a un pin existente desde su modal de detalle, para añadir evidencia fotográfica después de la creación del pin.

#### Acceptance Criteria

3.1 WHILE el Modal_Detalle de un pin está visible, THE Sistema SHALL mostrar un botón para agregar fotos al pin.

3.2 WHEN el usuario hace clic en el botón de agregar fotos, THE Sistema SHALL abrir un selector de archivos que permita elegir imágenes JPG o PNG.

3.3 WHEN el pin ya tiene 5 fotos, THE Sistema SHALL ocultar el botón de agregar fotos y mostrar un indicador de que se alcanzó el límite máximo.

3.4 WHEN el pin tiene menos de 5 fotos, THE Sistema SHALL permitir agregar fotos hasta completar el máximo de 5.

3.5 WHEN el usuario selecciona fotos desde el Modal_Detalle, THE Sistema SHALL enviar las fotos al servidor mediante una solicitud AJAX multipart con token CSRF.

3.6 WHEN la subida de fotos desde el Modal_Detalle es exitosa, THE Sistema SHALL actualizar la Grilla_Miniaturas sin recargar la página.

3.7 IF la subida de fotos falla desde el Modal_Detalle, THEN THE Sistema SHALL mostrar un mensaje de error dentro del modal sin cerrarlo.

### Requirement 4: Visualización de fotos en grilla de miniaturas

**User Story:** Como usuario staff, quiero ver las fotos del pin como una grilla de miniaturas en el modal de detalle, para tener una vista rápida de toda la evidencia fotográfica.

#### Acceptance Criteria

4.1 WHILE el Modal_Detalle está visible y el pin tiene fotos asociadas, THE Sistema SHALL mostrar una sección de Grilla_Miniaturas con las fotos del pin.

4.2 THE Sistema SHALL presentar la Grilla_Miniaturas en un diseño de 2 a 3 columnas según el ancho disponible del modal.

4.3 THE Sistema SHALL renderizar cada miniatura como una imagen cuadrada recortada (object-fit: cover) con bordes redondeados.

4.4 WHEN el pin no tiene fotos asociadas, THE Sistema SHALL ocultar la sección de Grilla_Miniaturas.

4.5 THE Sistema SHALL mostrar las fotos ordenadas por fecha de creación ascendente (las más antiguas primero).

### Requirement 5: Lightbox para visualización a tamaño completo

**User Story:** Como usuario staff, quiero poder hacer clic en una miniatura para ver la foto a tamaño completo, para inspeccionar los detalles de la evidencia fotográfica.

#### Acceptance Criteria

5.1 WHEN el usuario hace clic en una miniatura de la Grilla_Miniaturas, THE Sistema SHALL abrir un Lightbox que muestre la foto a tamaño completo centrada en la pantalla.

5.2 WHILE el Lightbox está abierto, THE Sistema SHALL mostrar un fondo oscuro semitransparente detrás de la imagen.

5.3 WHILE el Lightbox está abierto, THE Sistema SHALL mostrar un botón de cierre visible en la esquina superior derecha.

5.4 WHEN el usuario hace clic en el fondo oscuro del Lightbox, THE Sistema SHALL cerrar el Lightbox.

5.5 WHEN el usuario presiona la tecla Escape mientras el Lightbox está abierto, THE Sistema SHALL cerrar el Lightbox.

5.6 WHILE el Lightbox está abierto y el pin tiene múltiples fotos, THE Sistema SHALL mostrar flechas de navegación para ver la foto anterior y siguiente.

### Requirement 6: Eliminación individual de fotos

**User Story:** Como usuario staff, quiero poder eliminar fotos individuales de un pin desde el modal de detalle, para remover evidencia incorrecta o desactualizada.

#### Acceptance Criteria

6.1 WHILE el Modal_Detalle está visible y el pin tiene fotos, THE Sistema SHALL mostrar un botón de eliminar en cada miniatura de la Grilla_Miniaturas.

6.2 WHEN el usuario hace clic en el botón de eliminar de una foto, THE Sistema SHALL solicitar confirmación antes de proceder con la eliminación.

6.3 WHEN el usuario confirma la eliminación de una foto, THE Sistema SHALL enviar una solicitud AJAX POST al endpoint de eliminación con token CSRF.

6.4 WHEN la eliminación de una foto es exitosa, THE Sistema SHALL remover la miniatura de la Grilla_Miniaturas sin recargar la página.

6.5 WHEN la eliminación reduce el número de fotos por debajo de 5, THE Sistema SHALL volver a mostrar el botón de agregar fotos.

6.6 IF la eliminación de una foto falla, THEN THE Sistema SHALL mostrar un mensaje de error y mantener la miniatura visible.

### Requirement 7: Endpoints API para gestión de fotos

**User Story:** Como desarrollador, quiero endpoints REST para subir, listar y eliminar fotos de un pin, para que el frontend pueda gestionar las fotos mediante AJAX.

#### Acceptance Criteria

7.1 THE Sistema SHALL exponer un endpoint POST para subir fotos a un pin específico, aceptando datos multipart/form-data.

7.2 THE Sistema SHALL exponer un endpoint POST para eliminar una foto específica de un pin.

7.3 WHEN se recibe una solicitud de subida con más fotos de las permitidas (que sumadas a las existentes superen 5), THE Sistema SHALL rechazar la solicitud con HTTP 400 y un mensaje indicando cuántas fotos adicionales se permiten.

7.4 WHEN se recibe una solicitud de subida con archivos que no son JPG ni PNG, THE Sistema SHALL rechazar la solicitud con HTTP 400 y un mensaje indicando los formatos válidos.

7.5 WHEN se recibe una solicitud a un endpoint de fotos sin autenticación de staff, THE Sistema SHALL redirigir a la página de login (HTTP 302).

7.6 WHEN se intenta eliminar una foto que no existe, THE Sistema SHALL responder con HTTP 404.

7.7 WHEN la subida de fotos es exitosa, THE Sistema SHALL responder con HTTP 200 y un JSON con la lista de fotos subidas incluyendo id y URL de la imagen.

### Requirement 8: Seguridad y validación

**User Story:** Como administrador del sistema, quiero que las fotos se gestionen de forma segura, para proteger el sistema de archivos maliciosos y accesos no autorizados.

#### Acceptance Criteria

8.1 THE Sistema SHALL validar el tipo MIME real del archivo (no solo la extensión) para confirmar que es una imagen JPG o PNG válida.

8.2 THE Sistema SHALL proteger todos los endpoints de fotos con el decorador `@staff_member_required`.

8.3 THE Sistema SHALL validar que el pin pertenece al proyecto indicado en la URL antes de procesar operaciones de fotos.

8.4 IF se recibe un archivo con tipo MIME que no corresponde a JPG ni PNG, THEN THE Sistema SHALL rechazar el archivo con HTTP 400.
