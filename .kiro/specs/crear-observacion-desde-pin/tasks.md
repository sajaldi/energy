# Implementation Plan: Crear Observación desde Pin

## Overview

Extender el modal de creación de pin existente en `visor_plano_proyecto.html` para permitir crear una nueva observación inline. Los cambios se limitan a: (1) inyectar `DocumentoProyecto` como JSON en la vista, (2) agregar HTML del toggle + formulario inline en el modal, y (3) agregar JavaScript para gestión de modos, validación y creación encadenada AJAX. No se crean nuevos modelos, endpoints ni migraciones.

## Tasks

- [x] 1. Backend: Extender vista para inyectar DocumentoProyecto
  - [x] 1.1 Modificar la vista `visor_plano_proyecto` en `proyectos/views.py`
    - Importar `DocumentoProyecto` si no está importado
    - Consultar `DocumentoProyecto.objects.filter(proyecto=proyecto).select_related('documento')`
    - Serializar cada instancia a `{'id': doc_proy.id, 'texto': f"{doc_proy.documento.codigo} - {doc_proy.documento.titulo}"}`
    - Agregar `documentos_proyecto_json` al contexto con `json.dumps(documentos_proyecto_data, ensure_ascii=False)`
    - _Requirements: 6.1, 6.2_

  - [x] 1.2 Inyectar variables JavaScript en el template `visor_plano_proyecto.html`
    - Agregar `var CREAR_OBSERVACION_URL = "{% url 'proyectos:crear_observacion' proyecto.pk %}";` en el bloque `<script>` de datos inyectados
    - Agregar `var DOCUMENTOS_PROYECTO = {{ documentos_proyecto_json|safe }};`
    - _Requirements: 6.1, 6.3_

- [x] 2. Frontend: HTML del toggle y formulario inline en el modal
  - [x] 2.1 Agregar toggle de modos en el modal de creación de pin
    - Insertar grupo de radio buttons estilizados debajo del título del modal: "Seleccionar existente" (checked por defecto) y "Nueva observación"
    - Usar clase `.mode-toggle` con `.mode-option` para cada opción
    - Envolver el contenido existente del selector de observaciones en `<div id="section-existing" class="mode-section">`
    - _Requirements: 1.1, 1.2, 1.5_

  - [x] 2.2 Agregar sección del formulario inline para nueva observación
    - Crear `<div id="section-new" class="mode-section" style="display:none;">`
    - Campo `<textarea id="new-obs-texto">` con label "Texto de la observación *", placeholder "Describa la observación...", rows=3
    - Campo `<select id="select-documento">` con label "Documento vinculado *" y opción vacía "— Seleccionar documento —"
    - Divs de error inline: `<div class="field-error" id="error-obs-texto">` y `<div class="field-error" id="error-documento">`
    - Mensaje `<p id="no-docs-msg" style="display:none;">No hay documentos disponibles para este proyecto.</p>`
    - _Requirements: 2.1, 2.2, 6.3_

  - [x] 2.3 Agregar estilos CSS para el toggle y formulario inline
    - Estilos para `.mode-toggle`: display flex, gap, bordes redondeados
    - Estilos para `.mode-option`: padding, cursor pointer, transición, `.selected` con fondo activo
    - Estilos para `.field-error`: color rojo, font-size pequeño, margin-top
    - Estilos para `#section-new textarea` y `#section-new select`: ancho 100%, padding consistente
    - _Requirements: 1.1, 1.3, 3.1_

- [x] 3. Frontend: JavaScript para gestión de modos y validación
  - [x] 3.1 Implementar lógica de toggle entre modos
    - Variable `currentMode = 'existing'`
    - Listener en radio buttons `[name="pin-mode"]` que cambia visibilidad de `#section-existing` y `#section-new`
    - Al cambiar a modo "new": enfocar `#new-obs-texto`, popular `#select-documento` con `DOCUMENTOS_PROYECTO`
    - Si `DOCUMENTOS_PROYECTO` está vacío: mostrar `#no-docs-msg`, deshabilitar textarea y botón guardar
    - Preservar valores ingresados al cambiar de modo (no limpiar campos)
    - _Requirements: 1.2, 1.3, 1.4, 1.5, 2.5, 6.3_

  - [x] 3.2 Implementar validación del formulario inline
    - Función `validateNewObsForm()` que valida texto no vacío/whitespace y documento seleccionado
    - Función `showFieldError(elementId, message)` que muestra error inline
    - Función `clearFieldError(elementId)` que oculta error inline
    - Listeners `input` en textarea y `change` en select que limpian su error asociado al modificar
    - Retornar `false` si hay errores, impidiendo el envío
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 3.3 Implementar creación encadenada observación + pin
    - Función `saveNewObservationAndPin()` que: valida → deshabilita botones → POST crear observación → POST crear pin → maneja resultado
    - Payload observación: `{observacion, documento_proyecto_id, estado: 'ABIERTA', fecha_observacion: hoy}`
    - En éxito de observación: usar `id` retornado como `observacion_id` en payload del pin
    - En éxito completo: cerrar modal, agregar pin a `PINES_DATA`, llamar `renderizarPines(curPage)`
    - En fallo de observación: mostrar error en modal, mantener abierto
    - En fallo de pin (obs ya creada): mostrar mensaje de fallo parcial, agregar obs a `OBSERVACIONES_DISPONIBLES`
    - En cualquier caso: restaurar botones con `setButtonsLoading(false)` en bloque `finally`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 5.1, 5.2, 5.3_

  - [x] 3.4 Integrar el modo "Nueva observación" con el botón Guardar existente
    - Modificar el handler del botón "Guardar" para verificar `currentMode`
    - Si `currentMode === 'new'`: llamar `saveNewObservationAndPin()`
    - Si `currentMode === 'existing'`: ejecutar lógica existente de creación de pin con observación seleccionada
    - _Requirements: 1.2, 1.3, 4.1_

- [x] 4. Checkpoint - Verificar integración completa
  - Ensure all tests pass, ask the user if questions arise.

- [ ]* 5. Tests: Property-based tests
  - [ ]* 5.1 Write property test for DocumentoProyecto serialization
    - **Property 2: DocumentoProyecto serialization**
    - Usar Hypothesis para generar proyectos con N DocumentoProyecto, cada uno con documento.codigo y documento.titulo aleatorios
    - Verificar que la serialización produce lista con `id` correcto y `texto` = código + " - " + título
    - **Validates: Requirements 6.1, 2.2**

  - [ ]* 5.2 Write property test for whitespace-only text rejection
    - **Property 3: Whitespace-only text rejected**
    - Usar fast-check para generar strings de solo whitespace (espacios, tabs, newlines, vacíos)
    - Verificar que `validateNewObsForm()` retorna false y muestra error
    - **Validates: Requirements 3.1**

  - [ ]* 5.3 Write property test for invalid form prevents AJAX
    - **Property 4: Invalid form state prevents AJAX**
    - Usar fast-check para generar combinaciones de campos inválidos (texto vacío, documento no seleccionado, ambos)
    - Verificar que no se dispara ningún fetch/XMLHttpRequest
    - **Validates: Requirements 3.3**

  - [ ]* 5.4 Write property test for observation ID forwarded in chained creation
    - **Property 6: Observation ID forwarded in chained creation**
    - Usar fast-check para generar IDs numéricos positivos, mockear respuesta de crear observación con ese ID
    - Verificar que el segundo request incluye exactamente ese ID como `observacion_id`
    - **Validates: Requirements 4.2**

  - [ ]* 5.5 Write property test for buttons restored after any outcome
    - **Property 8: Buttons restored after any outcome**
    - Usar fast-check para generar escenarios (éxito, error obs, error pin, error red)
    - Verificar que en todos los casos los botones quedan habilitados al finalizar
    - **Validates: Requirements 5.3**

- [x] 6. Checkpoint final - Verificar todo el sistema
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate correctness properties defined in the design document
- No se crean modelos, migraciones ni endpoints nuevos — se reutiliza `crear_observacion_api` existente
- El template de referencia para patrones de inyección JSON es el mismo `visor_plano_proyecto.html`
- Se usa Hypothesis (Python/Django) para Property 2 y fast-check (JavaScript) para Properties 3, 4, 6, 8

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "2.1", "2.2", "2.3"] },
    { "id": 2, "tasks": ["3.1", "3.2"] },
    { "id": 3, "tasks": ["3.3", "3.4"] },
    { "id": 4, "tasks": ["5.1", "5.2", "5.3", "5.4", "5.5"] }
  ]
}
```
