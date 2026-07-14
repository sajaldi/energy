# Requirements Document

## Introduction

Esta funcionalidad agrega una nueva pestaña "Tareas" en la vista de detalle de proyecto (`/proyectos/proyecto/<id>/`), que presenta un tablero Kanban al estilo Microsoft Planner. El tablero permite a los usuarios gestionar visualmente las actividades del proyecto organizándolas en columnas según su estado (Pendiente, En Progreso, Completada, Bloqueada), con soporte para arrastrar y soltar tarjetas entre columnas.

## Glossary

- **Sistema_Kanban**: Componente de interfaz que renderiza el tablero Kanban dentro de la pestaña "Tareas" en la vista detalle del proyecto.
- **Tarjeta_Tarea**: Elemento visual dentro del tablero Kanban que representa una Actividad del proyecto, mostrando información resumida.
- **Columna_Estado**: Contenedor vertical en el tablero Kanban que agrupa las tarjetas por estado (Pendiente, En Progreso, Completada, Bloqueada).
- **Actividad**: Modelo existente de Django (`proyectos.Actividad`) que almacena las tareas de un proyecto con campos como nombre, estado, prioridad, responsable, fechas.
- **API_Tareas**: Endpoints REST del backend Django que gestionan las operaciones CRUD sobre actividades desde el tablero Kanban.
- **Vista_Detalle_Proyecto**: Página existente tipo SAP Object Page que muestra la información completa de un proyecto con múltiples pestañas.

## Requirements

### Requirement 1: Pestaña Tareas en la Vista de Detalle

**User Story:** Como usuario del sistema, quiero ver una pestaña "Tareas" en la vista de detalle del proyecto, para acceder al tablero Kanban sin salir del contexto del proyecto.

#### Acceptance Criteria

1. THE Vista_Detalle_Proyecto SHALL mostrar una pestaña con el texto "Tareas" en la barra de navegación de pestañas, ubicada después de la pestaña "Observaciones"
2. WHEN el usuario hace clic en la pestaña "Tareas", THE Sistema_Kanban SHALL mostrar el tablero Kanban con todas las actividades del proyecto organizadas en las cuatro columnas de estado (Pendiente, En Progreso, Completada, Bloqueada) en un tiempo máximo de 2 segundos desde el clic
3. THE Sistema_Kanban SHALL mantener el mismo estilo visual SAP Fiori (tipografía Inter, variables CSS --fiori-*) que las demás pestañas de la vista de detalle
4. IF el proyecto no tiene actividades registradas, THEN THE Sistema_Kanban SHALL mostrar un estado vacío con un mensaje indicando que no hay tareas y un botón "Crear primera tarea"

### Requirement 2: Estructura del Tablero Kanban

**User Story:** Como usuario del sistema, quiero visualizar las tareas en columnas según su estado, para entender de un vistazo el progreso de las actividades del proyecto.

#### Acceptance Criteria

1. THE Sistema_Kanban SHALL renderizar exactamente cuatro columnas en el siguiente orden de izquierda a derecha: "Pendiente", "En Progreso", "Completada" y "Bloqueada"
2. THE Columna_Estado SHALL mostrar el nombre del estado como encabezado y un contador con la cantidad de tarjetas que contiene
3. IF el ancho del viewport es inferior a 768px, THEN THE Sistema_Kanban SHALL permitir desplazamiento horizontal para acceder a todas las columnas
4. THE Columna_Estado SHALL ordenar las tarjetas por prioridad descendente (Crítica, Alta, Media, Baja) y, dentro de la misma prioridad, por fecha de creación ascendente
5. WHILE el proyecto no tiene actividades registradas, THE Sistema_Kanban SHALL mostrar un mensaje indicando que no hay tareas y un botón para crear la primera tarea
6. IF una columna contiene más de 10 tarjetas visibles, THEN THE Columna_Estado SHALL permitir desplazamiento vertical interno sin afectar la visibilidad del encabezado ni del contador

### Requirement 3: Tarjetas de Tarea

**User Story:** Como usuario del sistema, quiero ver información relevante de cada tarea en una tarjeta compacta, para evaluar rápidamente el estado y contexto de cada actividad.

#### Acceptance Criteria

1. THE Tarjeta_Tarea SHALL mostrar los siguientes campos de la actividad: nombre (título, truncado a 60 caracteres con puntos suspensivos si excede), prioridad (indicador visual de color), responsable asignado (nombre o "Sin asignar" si no tiene responsable), y fecha de fin (si existe)
2. THE Tarjeta_Tarea SHALL mostrar un indicador visual de prioridad mediante una franja de color de 4px en el borde izquierdo: azul (#0066cc) para Baja, amarillo (#f0ab00) para Media, naranja (#e67700) para Alta, rojo (#cc0000) para Crítica
3. THE Tarjeta_Tarea SHALL mostrar el porcentaje de avance como una barra de progreso de altura máxima 6px en la parte inferior de la tarjeta
4. IF la fecha de fin de una actividad ha pasado y el estado no es "Completada", THEN THE Tarjeta_Tarea SHALL mostrar la fecha en color rojo para indicar retraso

### Requirement 4: Creación de Tareas desde el Kanban

**User Story:** Como usuario del sistema, quiero crear nuevas tareas directamente desde el tablero Kanban, para agilizar la captura de trabajo sin cambiar de pestaña.

#### Acceptance Criteria

1. THE Columna_Estado SHALL mostrar un botón "+ Agregar Tarea" en la parte inferior de cada columna
2. WHEN el usuario hace clic en "+ Agregar Tarea", THE Sistema_Kanban SHALL mostrar un formulario modal con los campos: nombre (obligatorio, máximo 200 caracteres), descripción (opcional, máximo 2000 caracteres), prioridad (selector con valores Baja, Media, Alta, Crítica; por defecto Media), responsable (selector de usuarios activos del proyecto), fecha de inicio y fecha de fin
3. WHEN el usuario envía el formulario de creación con datos válidos, THE API_Tareas SHALL crear la actividad con el estado correspondiente a la columna donde se inició la creación
4. WHEN la API_Tareas confirma la creación exitosa, THE Sistema_Kanban SHALL agregar la nueva Tarjeta_Tarea en la columna correspondiente sin recargar la página completa y actualizar el contador de la columna
5. IF el usuario envía el formulario sin completar el campo nombre, THEN THE Sistema_Kanban SHALL mostrar un mensaje de validación indicando que el nombre es obligatorio
6. IF el usuario especifica una fecha de fin anterior a la fecha de inicio, THEN THE Sistema_Kanban SHALL mostrar un mensaje de validación indicando que la fecha de fin debe ser posterior a la fecha de inicio
7. IF la API_Tareas retorna un error durante la creación, THEN THE Sistema_Kanban SHALL mostrar una notificación de error y mantener el formulario modal abierto con los datos ingresados

### Requirement 5: Edición de Tareas

**User Story:** Como usuario del sistema, quiero editar los detalles de una tarea desde el tablero Kanban, para actualizar información sin navegar a otra vista.

#### Acceptance Criteria

1. WHEN el usuario hace clic en una Tarjeta_Tarea, THE Sistema_Kanban SHALL abrir un panel lateral o modal con todos los campos editables de la actividad: nombre (máximo 200 caracteres), descripción (máximo 2000 caracteres), estado (selector), prioridad (selector), responsable (selector de usuarios activos), fecha de inicio, fecha de fin, y porcentaje de avance (0-100)
2. WHEN el usuario guarda los cambios en el panel de edición, THE API_Tareas SHALL actualizar la actividad en el servidor
3. WHEN la API_Tareas confirma la actualización exitosa, THE Sistema_Kanban SHALL reflejar los cambios en la Tarjeta_Tarea y actualizar los contadores de las columnas afectadas
4. IF el estado de la actividad cambió durante la edición, THEN THE Sistema_Kanban SHALL reubicar la tarjeta en la columna correspondiente al nuevo estado
5. IF ocurre un error al guardar los cambios, THEN THE Sistema_Kanban SHALL mostrar una notificación de error al usuario y mantener los datos previos en la tarjeta
6. WHEN el usuario cierra el panel de edición sin guardar (botón cancelar o clic fuera del panel), THE Sistema_Kanban SHALL descartar los cambios no guardados y cerrar el panel

### Requirement 6: Eliminación de Tareas

**User Story:** Como usuario del sistema, quiero eliminar tareas desde el tablero Kanban, para remover actividades que ya no son necesarias.

#### Acceptance Criteria

1. WHEN el usuario abre el panel de edición de una tarea, THE Sistema_Kanban SHALL mostrar un botón "Eliminar" visualmente separado de los botones de acción primaria y renderizado con el color de alerta del tema activo
2. WHEN el usuario hace clic en "Eliminar", THE Sistema_Kanban SHALL mostrar un diálogo de confirmación SweetAlert2 que incluya el nombre de la tarea y dos opciones: confirmar eliminación y cancelar
3. WHEN el usuario confirma la eliminación en el diálogo, THE API_Tareas SHALL eliminar la actividad del servidor y THE Sistema_Kanban SHALL remover la Tarjeta_Tarea de la columna con una animación de salida de duración máxima 300ms
4. IF ocurre un error al eliminar la actividad, THEN THE Sistema_Kanban SHALL mostrar una notificación toast de error durante 5 segundos indicando que la tarea no pudo ser eliminada, y mantener la Tarjeta_Tarea visible en su posición original dentro del tablero
5. WHEN el usuario cancela la eliminación en el diálogo de confirmación, THE Sistema_Kanban SHALL cerrar el diálogo y mantener la Tarjeta_Tarea sin modificaciones en el tablero

### Requirement 7: Arrastrar y Soltar (Drag & Drop)

**User Story:** Como usuario del sistema, quiero mover tareas entre columnas arrastrando las tarjetas, para cambiar el estado de las actividades de forma intuitiva y rápida.

#### Acceptance Criteria

1. THE Tarjeta_Tarea SHALL ser arrastrable (draggable) mediante la API nativa de HTML5 Drag and Drop
2. WHEN el usuario arrastra una tarjeta sobre una Columna_Estado diferente, THE Columna_Estado de destino SHALL mostrar un indicador visual (borde resaltado de 2px con color primario del tema) para indicar que acepta la tarjeta
3. WHEN el usuario suelta una tarjeta en una Columna_Estado diferente, THE API_Tareas SHALL actualizar el estado de la actividad al estado correspondiente de la columna destino
4. WHEN la API_Tareas confirma la actualización del estado, THE Sistema_Kanban SHALL mantener la tarjeta en la nueva columna y actualizar los contadores de ambas columnas (origen y destino)
5. IF ocurre un error al actualizar el estado mediante drag & drop, THEN THE Sistema_Kanban SHALL revertir la tarjeta a su columna original y mostrar una notificación de error
6. WHILE el usuario arrastra una tarjeta, THE Tarjeta_Tarea SHALL mostrar una opacidad reducida (0.5) en su posición original para indicar que está siendo movida
7. WHEN el usuario suelta una tarjeta en la misma columna de origen, THE Sistema_Kanban SHALL no realizar ninguna llamada a la API y mantener la tarjeta en su posición

### Requirement 8: Sincronización con Datos Existentes

**User Story:** Como usuario del sistema, quiero que el tablero Kanban refleje las mismas actividades que el cronograma y la tabla de actividades, para mantener coherencia en toda la vista del proyecto.

#### Acceptance Criteria

1. THE Sistema_Kanban SHALL utilizar el modelo Actividad existente sin crear modelos de datos adicionales
2. THE Sistema_Kanban SHALL mostrar todas las actividades del proyecto actualmente visualizado, incluyendo como mínimo los campos: nombre, estado, prioridad, asignado_a, fecha_inicio, fecha_fin y porcentaje_avance, reflejando los mismos datos visibles en la pestaña "Cronograma / Actividades"
3. WHEN el usuario mueve una tarjeta entre columnas del tablero Kanban, THE Sistema_Kanban SHALL actualizar el campo `estado` de la Actividad correspondiente al valor de la columna destino (PENDIENTE, EN_PROGRESO, COMPLETADA o BLOQUEADA), y el cambio SHALL ser visible al navegar a la pestaña "Cronograma / Actividades" sin necesidad de recargar la página completa
4. WHEN el usuario crea o modifica campos de una tarea desde el tablero Kanban, THE Sistema_Kanban SHALL invocar los endpoints existentes de actividades (`crear_actividad_api`, `actualizar_actividad_api`, `delete_actividad_api`) manteniendo la misma estructura de datos del modelo Actividad
5. IF una operación de creación, actualización o eliminación desde el tablero Kanban falla (error de red o respuesta con status distinto a 200), THEN THE Sistema_Kanban SHALL mostrar un mensaje de error indicando que la operación no se completó, revertir visualmente la tarjeta a su posición o estado anterior, y no persistir el cambio en el modelo Actividad

### Requirement 9: Filtrado y Búsqueda en el Tablero

**User Story:** Como usuario del sistema, quiero filtrar las tareas del tablero por responsable o prioridad, para enfocarme en las tareas que me interesan.

#### Acceptance Criteria

1. THE Sistema_Kanban SHALL mostrar una barra de filtros sobre las columnas del tablero con un selector de responsable (lista de usuarios miembros del proyecto que tienen al menos una actividad asignada) y un selector de prioridad (Baja, Media, Alta, Crítica), ambos con una opción por defecto "Todos" que indica sin filtro aplicado
2. WHEN el usuario selecciona un valor en cualquiera de los selectores de filtro, THE Sistema_Kanban SHALL ocultar las tarjetas que no coincidan con todos los criterios seleccionados simultáneamente (lógica AND entre filtros) y actualizar el contador numérico visible en el encabezado de cada columna para reflejar únicamente las tarjetas visibles
3. IF los filtros aplicados no coinciden con ninguna tarjeta en una columna, THEN THE Sistema_Kanban SHALL mostrar un mensaje indicando que no hay tarjetas que coincidan con los filtros en dicha columna
4. WHEN el usuario restablece un selector a la opción "Todos", THE Sistema_Kanban SHALL mostrar nuevamente todas las tarjetas que coincidan con los filtros restantes activos y actualizar los contadores de cada columna
5. THE Sistema_Kanban SHALL incluir un botón "Limpiar filtros" que restablezca todos los selectores a la opción "Todos" y muestre todas las tarjetas del proyecto con los contadores actualizados
