# Implementation Plan: Tablero Kanban de Tareas del Proyecto

## Overview

Implementar un tablero Kanban al estilo Microsoft Planner dentro de la pestaña "Tareas" en la vista de detalle de proyecto. Se reutiliza el modelo `Actividad` existente, se agrega un endpoint GET para actividades agrupadas, se modifica `crear_actividad_api` para aceptar `estado` y `asignado_id`, y se construye todo el frontend con vanilla JS + HTML5 Drag & Drop.

## Tasks

- [x] 1. Backend: Nuevo endpoint y modificación de endpoint existente
  - [x] 1.1 Crear el endpoint `kanban_actividades_api` en `proyectos/views.py`
    - Agregar la función `kanban_actividades_api(request, pk)` con decorador `@staff_member_required`
    - Retornar actividades del proyecto agrupadas por estado (PENDIENTE, EN_PROGRESO, COMPLETADA, BLOQUEADA)
    - Incluir `select_related('asignado_a')` para optimizar queries
    - Ordenar por prioridad descendente y fecha de creación ascendente
    - Incluir lista de responsables que tienen actividades asignadas
    - Estructura de respuesta JSON: `{status, actividades: {PENDIENTE:[], ...}, responsables: [{id, nombre}]}`
    - _Requirements: 1.2, 2.1, 2.4, 8.2, 9.1_

  - [x] 1.2 Registrar la URL del nuevo endpoint en `proyectos/urls.py`
    - Agregar `path('proyecto/<int:pk>/kanban/api/', views.kanban_actividades_api, name='kanban_actividades_api')`
    - _Requirements: 1.2, 8.4_

  - [x] 1.3 Modificar `crear_actividad_api` en `proyectos/views.py` para aceptar `estado` y `asignado_id`
    - Cambiar `estado='PENDIENTE'` hardcodeado por `data.get('estado', 'PENDIENTE')`
    - Cambiar `asignado_a=request.user` hardcodeado por lógica que use `data.get('asignado_id')` con fallback a `request.user`
    - Validar que el estado recibido esté en la lista ESTADOS válidos
    - Incluir `asignado_a_id` y `asignado_a_nombre` en la respuesta JSON
    - _Requirements: 4.3, 8.4_

  - [ ]* 1.4 Escribir tests de integración Django para los endpoints
    - Test GET `kanban_actividades_api` retorna actividades agrupadas correctamente
    - Test POST `crear_actividad_api` acepta `estado` y `asignado_id`
    - Test que la respuesta respeta el ordenamiento por prioridad
    - _Requirements: 1.2, 2.4, 4.3, 8.2_

- [x] 2. Frontend: Estructura HTML de la pestaña Tareas y el tablero Kanban
  - [x] 2.1 Agregar la pestaña "Tareas" en la barra de navegación de `proyecto_detalle_fiori.html`
    - Insertar `<div class="sap-tab" data-target="tareas">Tareas</div>` después de la pestaña "Observaciones" en la `<nav class="sap-tab-bar">`
    - _Requirements: 1.1_

  - [x] 2.2 Agregar la sección HTML del tablero Kanban en `proyecto_detalle_fiori.html`
    - Crear `<section id="tareas" class="sap-section">` con:
      - Barra de filtros (select responsable, select prioridad, botón limpiar filtros)
      - Contenedor `.kanban-board` con 4 columnas (PENDIENTE, EN_PROGRESO, COMPLETADA, BLOQUEADA)
      - Cada columna con header (título + contador), body (scroll para tarjetas), y botón "+ Agregar Tarea"
      - Estado vacío con mensaje y botón "Crear primera tarea"
    - _Requirements: 1.4, 2.1, 2.2, 2.5, 4.1, 9.1, 9.5_

  - [x] 2.3 Agregar el modal de creación de tareas en `proyecto_detalle_fiori.html`
    - Modal con campos: nombre (obligatorio, max 200), descripción (opcional, max 2000), prioridad (selector, default MEDIA), responsable (selector usuarios activos), fecha inicio, fecha fin
    - Campo oculto para almacenar el estado de la columna de origen
    - Botones: Cancelar y Crear Tarea
    - _Requirements: 4.2, 4.5, 4.6_

  - [x] 2.4 Agregar el panel de edición de tareas en `proyecto_detalle_fiori.html`
    - Panel lateral (offcanvas o modal) con todos los campos editables: nombre, descripción, estado, prioridad, responsable, fecha inicio, fecha fin, porcentaje avance (0-100)
    - Botón "Eliminar" visualmente separado con color de alerta
    - Botones: Cancelar y Guardar cambios
    - _Requirements: 5.1, 5.6, 6.1_

- [x] 3. Frontend: Estilos CSS del tablero Kanban
  - [x] 3.1 Agregar estilos CSS para el tablero Kanban en el bloque `<style>` de `proyecto_detalle_fiori.html`
    - `.kanban-board`: display flex, gap, overflow-x auto para responsive < 768px
    - `.kanban-column`: flex 0 0 280px, background #f8f9fa, border-radius, height máxima con scroll vertical
    - `.kanban-column-header`: flex con título y contador, sticky top
    - `.kanban-column-body`: overflow-y auto, min-height para drop zone
    - `.kanban-card`: background white, border-radius 8px, padding, margin-bottom, cursor grab, shadow
    - `.card-priority-indicator`: width 4px, posición absoluta lado izquierdo, colores por prioridad
    - `.card-progress`: height 6px, border-radius, background #e9ecef, barra interna con color primario
    - `.kanban-card.dragging`: opacity 0.5
    - `.kanban-column.drag-over`: borde 2px con color primario del tema
    - `.kanban-filters`: flex, gap, margin-bottom
    - `.kanban-add-btn`: botón al pie de cada columna
    - Indicador visual fecha vencida (color rojo #cc0000)
    - _Requirements: 1.3, 2.3, 2.6, 3.2, 3.3, 3.4, 7.2, 7.6_

- [x] 4. Checkpoint - Verificar estructura HTML y CSS
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Frontend: Módulo JavaScript KanbanBoard - Carga y renderizado
  - [x] 5.1 Implementar el módulo `KanbanBoard` con estado inicial y método `init(proyectoId)` en `proyecto_detalle_fiori.html`
    - Definir objeto `KanbanBoard` con `state: {actividades, filtros, responsables, proyectoId}`
    - Método `init()`: guardar proyectoId, bind events de la pestaña, llamar `loadActividades()` al activar pestaña "Tareas"
    - URL base: `/proyectos/proyecto/${proyectoId}/kanban/api/`
    - _Requirements: 1.2_

  - [x] 5.2 Implementar `loadActividades()` y `render()` para fetch y renderizado del tablero
    - `loadActividades()`: fetch GET al endpoint, actualizar `state.actividades` y `state.responsables`, llamar `render()`
    - Manejo de error: mostrar mensaje "Error al cargar las tareas" con botón "Reintentar"
    - `render()`: poblar selector de responsables, llamar `renderColumn()` para cada estado
    - Mostrar/ocultar estado vacío según haya actividades o no
    - _Requirements: 1.2, 1.4, 2.1, 2.5, 9.1_

  - [x] 5.3 Implementar `renderColumn(estado, items)` y `renderCard(actividad)` 
    - `renderColumn()`: limpiar body de la columna, iterar items filtrados, insertar HTML de cada tarjeta, actualizar contador
    - `renderCard()`: generar HTML con nombre truncado (57 + "..." si > 60 chars), franja de prioridad (BAJA=#0066cc, MEDIA=#f0ab00, ALTA=#e67700, CRITICA=#cc0000), responsable, fecha fin (rojo si vencida y no completada), barra de progreso
    - Helper `truncateName(nombre, 60)`: retorna primeros 57 chars + "..." si excede
    - Helper `getPriorityColor(prioridad)`: mapeo prioridad→color
    - Helper `isOverdue(fechaFin, estado)`: true si fecha pasada y estado != COMPLETADA
    - _Requirements: 2.2, 2.4, 3.1, 3.2, 3.3, 3.4_

  - [ ]* 5.4 Escribir property tests para funciones puras del KanbanBoard
    - **Property 2: Ordenamiento por prioridad y fecha de creación**
    - **Property 3: Truncamiento de nombre**
    - **Property 4: Mapeo prioridad-color**
    - **Property 5: Fecha de vencimiento con indicador de retraso**
    - **Validates: Requirements 2.4, 3.1, 3.2, 3.4**

- [x] 6. Frontend: CRUD de tareas (Crear, Editar, Eliminar)
  - [x] 6.1 Implementar creación de tareas: `openCreateModal(estado)` y `submitCreate(formData)`
    - `openCreateModal()`: mostrar modal, pre-seleccionar estado de la columna, poblar selector responsable
    - `submitCreate()`: validar nombre obligatorio, validar fecha_fin >= fecha_inicio, POST a `/proyectos/api/crear-actividad/` con `{proyecto_id, nombre, descripcion, prioridad, estado, fecha_inicio, fecha_fin, asignado_id}`
    - En éxito: cerrar modal, agregar tarjeta a la columna, actualizar contador
    - En error: toast SweetAlert2, mantener modal abierto
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

  - [x] 6.2 Implementar edición de tareas: `openEditPanel(actividadId)` y `submitEdit(actividadId, data)`
    - `openEditPanel()`: fetch detalle de actividad desde `/proyectos/api/actividad/{id}/detalle/`, poblar formulario del panel
    - `submitEdit()`: validar campos, POST a `/proyectos/api/actualizar-actividad/{id}/` con campos modificados
    - En éxito: cerrar panel, actualizar tarjeta en el DOM, reubicar si cambió estado, actualizar contadores
    - En error: toast SweetAlert2, mantener datos previos
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [x] 6.3 Implementar eliminación de tareas: `confirmDelete(actividadId)`
    - Mostrar SweetAlert2 de confirmación con nombre de la tarea y botones "Sí, eliminar" / "Cancelar"
    - En confirmación: POST/DELETE a `/proyectos/proyecto/{pk}/actividades/{act_id}/delete/`
    - En éxito: remover tarjeta con animación (max 300ms), actualizar contador
    - En error: toast de error 5s, mantener tarjeta visible
    - En cancelar: cerrar diálogo sin cambios
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 7. Frontend: Drag & Drop entre columnas
  - [x] 7.1 Implementar handlers de Drag & Drop en `KanbanBoard`
    - `handleDragStart(e, cardEl)`: setDragImage, setData con actividadId y columna origen, agregar clase `.dragging` (opacity 0.5)
    - `handleDragOver(e, columnEl)`: preventDefault, agregar clase `.drag-over` (borde 2px color primario)
    - `handleDragLeave(e, columnEl)`: remover clase `.drag-over`
    - `handleDrop(e, columnEl)`: obtener estado destino, si es misma columna → no-op sin API call; si es diferente → mover tarjeta visualmente (optimistic UI), POST a `/proyectos/api/actualizar-actividad/{id}/` con `{estado: nuevoEstado}`
    - `handleDragEnd(e, cardEl)`: remover clase `.dragging`, limpiar estilos de todas las columnas
    - En éxito: actualizar contadores de ambas columnas
    - En error: revertir tarjeta a columna original, toast de error
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_

  - [ ]* 7.2 Escribir property tests para lógica de Drag & Drop
    - **Property 1: Distribución estado-columna**
    - **Property 7: Soltar en misma columna no genera llamada API**
    - **Validates: Requirements 1.2, 2.2, 7.7**

- [x] 8. Frontend: Filtrado por responsable y prioridad
  - [x] 8.1 Implementar `applyFilters()`, `clearFilters()` y `updateCounters()`
    - `applyFilters()`: leer valores de selectores, ocultar tarjetas que no cumplan TODOS los filtros (AND), mostrar mensaje "sin resultados" por columna si aplica
    - `clearFilters()`: resetear selectores a "Todos", mostrar todas las tarjetas
    - `updateCounters()`: contar tarjetas visibles por columna, actualizar texto del contador en header
    - Bind events `change` en selectores de filtro y `click` en botón limpiar
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [ ]* 8.2 Escribir property test para filtrado AND con contadores
    - **Property 8: Filtrado AND con actualización de contadores**
    - **Validates: Requirements 9.2, 9.4, 2.2**

- [x] 9. Checkpoint - Verificar funcionalidad completa del Kanban
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Integración final y sincronización
  - [x] 10.1 Integrar el sistema de pestañas para que "Tareas" cargue datos al activarse
    - Conectar el listener de clic de pestaña existente (sistema `data-target`) con `KanbanBoard.init()`
    - Lazy loading: solo cargar datos la primera vez que se activa la pestaña
    - Asegurar que cambios hechos en Kanban se reflejen si el usuario navega a "Cronograma / Actividades" (refrescar tabla)
    - _Requirements: 1.2, 8.3_

  - [x] 10.2 Verificar coherencia con pestaña "Cronograma / Actividades" existente
    - Cuando se crea/actualiza/elimina desde el Kanban, el estado en la tabla de actividades debe reflejar el cambio
    - Si se vuelve a la pestaña "Cronograma / Actividades", refrescar datos o invalidar caché
    - _Requirements: 8.2, 8.3, 8.4_

  - [ ]* 10.3 Escribir property test para rollback en caso de error
    - **Property 9: Rollback en caso de error de API**
    - **Validates: Requirements 7.5, 8.5, 4.7, 5.5, 6.4**

  - [ ]* 10.4 Escribir property test para validación de fechas
    - **Property 6: Validación de fechas en formulario**
    - **Validates: Requirements 4.6**

- [x] 11. Final checkpoint - Verificar integración completa
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- El modelo `Actividad` existente no requiere migraciones
- Los endpoints existentes (`actualizar_actividad_api`, `delete_actividad_api`) ya manejan los campos necesarios
- El endpoint `activity_detail_api` ya existe y retorna toda la información necesaria para el panel de edición
- SweetAlert2 ya está incluido en el template, no requiere instalación adicional
- La URL del endpoint de eliminación es: `/proyectos/proyecto/{pk}/actividades/{act_id}/delete/`
- La URL del endpoint de actualización es: `/proyectos/api/actualizar-actividad/{id}/`
- La URL del endpoint de creación es: `/proyectos/api/crear-actividad/`
- La URL del endpoint de detalle es: `/proyectos/api/actividad/{id}/detalle/`

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3", "2.1"] },
    { "id": 2, "tasks": ["1.4", "2.2", "2.3", "2.4"] },
    { "id": 3, "tasks": ["3.1"] },
    { "id": 4, "tasks": ["5.1"] },
    { "id": 5, "tasks": ["5.2", "5.3"] },
    { "id": 6, "tasks": ["5.4", "6.1", "6.2", "6.3"] },
    { "id": 7, "tasks": ["7.1", "8.1"] },
    { "id": 8, "tasks": ["7.2", "8.2", "10.1"] },
    { "id": 9, "tasks": ["10.2", "10.3", "10.4"] }
  ]
}
```
