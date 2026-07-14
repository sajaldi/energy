# Requirements Document

## Introduction

Esta funcionalidad extiende el modal de creación de pin en el visor de planos PDF de proyecto, permitiendo al usuario crear una nueva observación de forma inline (sin salir del visor) y vincularla automáticamente como pin en el plano. Actualmente el modal solo permite seleccionar una observación existente; con este cambio, el usuario podrá alternar entre seleccionar una existente o crear una nueva directamente desde el mismo modal.

El flujo de creación inline encadena dos operaciones: primero crea la observación vía AJAX usando el endpoint existente `crear_observacion_api`, y luego crea el pin vinculado a la observación recién creada. Los campos por defecto (estado ABIERTA, fecha de hoy) simplifican la experiencia para el caso más común.

## Glossary

- **Modal_Crear_Pin**: Diálogo modal existente que se muestra al usuario cuando elige agregar un pin de observación en el visor de planos PDF del proyecto.
- **Formulario_Inline**: Sección dentro del Modal_Crear_Pin que permite ingresar los datos de una nueva observación sin navegar a otra página.
- **Visor_Plano_Proyecto**: Página web que renderiza un plano PDF de un proyecto con capacidades de zoom, pan, navegación de páginas y capa de pines.
- **ObservacionProyecto**: Modelo que almacena una observación asociada a un proyecto, con campos: proyecto (FK), documento_proyecto (FK a DocumentoProyecto), observacion (texto), estado (ABIERTA, EN_PROCESO, RESUELTA, CERRADA), fecha_observacion (date), usuario (FK).
- **DocumentoProyecto**: Modelo que representa la relación entre un proyecto y un documento vinculado, requerido como referencia para cada observación.
- **Pin_Observacion**: Marcador visual posicionado sobre el plano PDF en coordenadas específicas, vinculado a una ObservacionProyecto mediante el modelo PinObservacionProyecto.
- **Sistema**: El conjunto de backend (Django) y frontend (JavaScript vanilla) que implementa la funcionalidad.
- **Endpoint_Crear_Observacion**: Endpoint existente en `proyecto/<pk>/observaciones/crear/` que crea una ObservacionProyecto dado un payload JSON.

## Requirements

### Requirement 1: Toggle entre selección existente y creación nueva en el modal

**User Story:** Como usuario del visor de planos, quiero poder elegir entre seleccionar una observación existente o crear una nueva directamente en el modal de pin, para no tener que salir del visor cuando necesito documentar un hallazgo nuevo.

#### Acceptance Criteria

1. WHEN el Modal_Crear_Pin se abre, THE Sistema SHALL mostrar dos opciones de modo: "Seleccionar existente" y "Nueva observación".
2. WHEN el usuario selecciona el modo "Seleccionar existente", THE Sistema SHALL mostrar el selector dropdown de observaciones disponibles (comportamiento actual).
3. WHEN el usuario selecciona el modo "Nueva observación", THE Sistema SHALL mostrar el Formulario_Inline para crear una nueva observación.
4. WHEN el usuario cambia de modo, THE Sistema SHALL ocultar la sección del modo anterior y mostrar la sección del modo seleccionado, preservando los valores ingresados en cada sección.
5. THE Sistema SHALL iniciar el Modal_Crear_Pin en el modo "Seleccionar existente" por defecto.

### Requirement 2: Formulario inline para nueva observación

**User Story:** Como usuario del visor de planos, quiero un formulario simple para ingresar los datos mínimos de una observación nueva, para que la creación sea rápida sin campos innecesarios.

#### Acceptance Criteria

1. THE Formulario_Inline SHALL contener un campo de texto multilínea para el texto de la observación, marcado como obligatorio.
2. THE Formulario_Inline SHALL contener un selector de DocumentoProyecto que muestre los documentos vinculados al proyecto actual.
3. THE Formulario_Inline SHALL preseleccionar el estado "ABIERTA" como valor por defecto sin mostrarlo como campo editable.
4. THE Formulario_Inline SHALL preseleccionar la fecha actual (hoy) como fecha_observacion sin mostrarlo como campo editable.
5. WHEN el Formulario_Inline se muestra, THE Sistema SHALL enfocar automáticamente el campo de texto de la observación.
6. THE Sistema SHALL inyectar la lista de DocumentoProyecto del proyecto como datos JSON en el template del visor para popular el selector sin solicitudes AJAX adicionales.

### Requirement 3: Validación del formulario inline

**User Story:** Como usuario del visor de planos, quiero recibir retroalimentación clara cuando faltan datos obligatorios, para corregir errores antes de enviar.

#### Acceptance Criteria

1. WHEN el usuario intenta guardar con el campo de texto de observación vacío, THE Sistema SHALL mostrar un mensaje de error junto al campo indicando que el texto es obligatorio.
2. WHEN el usuario intenta guardar sin haber seleccionado un DocumentoProyecto, THE Sistema SHALL mostrar un mensaje de error junto al selector indicando que el documento es obligatorio.
3. WHEN el Sistema detecta un error de validación en el Formulario_Inline, THE Sistema SHALL impedir el envío de la solicitud al backend.
4. WHEN el usuario corrige un campo con error y modifica su contenido, THE Sistema SHALL ocultar el mensaje de error de ese campo.

### Requirement 4: Creación encadenada observación + pin

**User Story:** Como usuario del visor de planos, quiero que al guardar el pin con una nueva observación, el sistema cree primero la observación y luego el pin automáticamente, para obtener un resultado atómico sin pasos manuales intermedios.

#### Acceptance Criteria

1. WHEN el usuario confirma la creación del pin en modo "Nueva observación", THE Sistema SHALL enviar primero una solicitud AJAX POST al Endpoint_Crear_Observacion con los datos de la nueva observación (texto, documento_proyecto_id, fecha de hoy, estado ABIERTA).
2. WHEN el Endpoint_Crear_Observacion responde exitosamente con el ID de la nueva observación, THE Sistema SHALL enviar una segunda solicitud AJAX POST al endpoint de creación de pin con las coordenadas (x, y), la página, el color, la nota y el ID de la observación recién creada.
3. WHEN ambas solicitudes se completan exitosamente, THE Sistema SHALL cerrar el Modal_Crear_Pin y agregar el marcador visual del pin en el plano sin recargar la página.
4. WHEN ambas solicitudes se completan exitosamente, THE Sistema SHALL agregar la nueva observación al selector de observaciones vinculadas y removerla de las disponibles (actualización del estado local).
5. IF la solicitud de creación de observación falla, THEN THE Sistema SHALL mostrar el mensaje de error en el Modal_Crear_Pin y mantener el modal abierto sin crear el pin.
6. IF la solicitud de creación de pin falla después de haber creado la observación exitosamente, THEN THE Sistema SHALL mostrar un mensaje de error indicando que la observación fue creada pero el pin no pudo vincularse, y sugerir seleccionarla desde el modo "Seleccionar existente".

### Requirement 5: Indicador de estado durante la creación

**User Story:** Como usuario del visor de planos, quiero ver un indicador visual de que el sistema está procesando mi solicitud, para saber que la operación está en curso.

#### Acceptance Criteria

1. WHILE la solicitud de creación de observación o de pin está en curso, THE Sistema SHALL deshabilitar el botón "Guardar" y mostrar un indicador de carga (spinner o texto "Guardando...").
2. WHILE la solicitud está en curso, THE Sistema SHALL deshabilitar el botón "Cancelar" para evitar interrupciones del flujo.
3. WHEN la solicitud finaliza (exitosamente o con error), THE Sistema SHALL restaurar el estado habilitado de los botones.

### Requirement 6: Contexto de datos para el formulario inline

**User Story:** Como desarrollador, quiero que la vista del visor inyecte los datos de documentos del proyecto en el template, para que el formulario inline funcione sin solicitudes AJAX adicionales en la carga.

#### Acceptance Criteria

1. WHEN el Visor_Plano_Proyecto renderiza la página, THE Sistema SHALL incluir en el contexto del template una lista JSON de los DocumentoProyecto del proyecto actual con campos: id y texto descriptivo (código y título del documento).
2. THE Sistema SHALL consultar los DocumentoProyecto mediante la relación `proyecto.documentos_proyecto` con select_related al documento para optimizar queries.
3. IF el proyecto no tiene DocumentoProyecto asociados, THEN THE Sistema SHALL pasar una lista vacía y el Formulario_Inline SHALL mostrar un mensaje indicando que no hay documentos disponibles y deshabilitar la opción de crear nueva observación.
