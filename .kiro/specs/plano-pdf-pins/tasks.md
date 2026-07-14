# Implementation Plan: Plano PDF Pins

## Overview

Implementar un sistema de pines visuales sobre planos PDF de proyecto que vincule cada pin a una observación existente. Se crea el modelo `PinObservacionProyecto` en la app `proyectos`, se implementan 3 endpoints API (listar, crear, eliminar), se extiende la vista `visor_plano_proyecto` para inyectar datos JSON, y se agrega al template la capa de pines interactiva con menú contextual, modal de creación y modal de detalle, siguiendo el patrón existente en `core/templates/activos/visor_pdf_plano.html`.

## Tasks

- [x] 1. Backend: Modelo PinObservacionProyecto y migración
  - [x] 1.1 Crear el modelo `PinObservacionProyecto` en `proyectos/models.py`
    - Importar `ColorField` desde `colorfield.fields`
    - Definir modelo con campos: `plano` (FK a PlanoProyecto, CASCADE, related_name='pines_observacion'), `observacion` (FK a ObservacionProyecto, CASCADE, related_name='pines_plano'), `coordenada_x` (FloatField), `coordenada_y` (FloatField), `pagina` (PositiveIntegerField default=1), `color` (ColorField default='#EF4444'), `nota` (TextField blank=True), `creado_en` (DateTimeField auto_now_add=True)
    - Configurar `class Meta`: `unique_together = ('plano', 'observacion')`, verbose_name="Pin de Observación en Proyecto", verbose_name_plural="Pines de Observación en Proyecto"
    - Implementar `__str__` retornando descripción del pin
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x] 1.2 Generar y aplicar la migración de Django
    - Ejecutar `python manage.py makemigrations proyectos`
    - Verificar migración creada en `proyectos/migrations/`
    - Ejecutar `python manage.py migrate`
    - _Requirements: 1.1_

- [x] 2. Backend: Endpoints API de pines
  - [x] 2.1 Implementar `listar_pines_plano_api` en `proyectos/views.py`
    - Decorador `@staff_member_required`
    - Aceptar solo método GET, retornar 405 para otros
    - Obtener proyecto por `pk` y plano por `plano_id` con get_object_or_404, validar que plano pertenece al proyecto
    - Serializar cada pin: id, x (coordenada_x), y (coordenada_y), pagina, color, nota, observacion_id, observacion_texto (primeros 80 chars de observacion.observacion), observacion_estado, observacion_usuario (get_full_name), observacion_fecha (ISO)
    - Retornar JSON: `{"status": "success", "pines": [...]}`
    - _Requirements: 6.1, 6.4_

  - [x] 2.2 Implementar `crear_pin_plano_api` en `proyectos/views.py`
    - Decorador `@staff_member_required`
    - Aceptar solo método POST, retornar 405 para otros
    - Obtener proyecto y plano con get_object_or_404
    - Parsear JSON del body: x, y, pagina, observacion_id, color, nota
    - Validar que la observación existe y pertenece al mismo proyecto que el plano (HTTP 400 si no)
    - Validar unicidad plano+observación: si ya existe, retornar HTTP 400 con mensaje "Esta observación ya está vinculada a este plano."
    - Crear `PinObservacionProyecto` con los datos recibidos
    - Retornar JSON: `{"status": "success", "pin": {id, x, y, pagina, color, nota, observacion_id, observacion_texto, observacion_estado}}`
    - _Requirements: 6.2, 6.4, 6.5, 3.6, 3.7_

  - [x] 2.3 Implementar `eliminar_pin_plano_api` en `proyectos/views.py`
    - Decorador `@staff_member_required`
    - Aceptar solo método POST, retornar 405 para otros
    - Obtener proyecto, plano y pin con get_object_or_404, validar cadena de pertenencia
    - Eliminar el pin (solo el registro PinObservacionProyecto, NO la observación)
    - Retornar JSON: `{"status": "success"}`
    - _Requirements: 6.3, 6.4, 5.5_

  - [x] 2.4 Registrar las URLs de los endpoints en `proyectos/urls.py`
    - Agregar `path('proyecto/<int:pk>/planos/<int:plano_id>/pines/', views.listar_pines_plano_api, name='listar_pines_plano_api')`
    - Agregar `path('proyecto/<int:pk>/planos/<int:plano_id>/pines/crear/', views.crear_pin_plano_api, name='crear_pin_plano_api')`
    - Agregar `path('proyecto/<int:pk>/planos/<int:plano_id>/pines/<int:pin_id>/eliminar/', views.eliminar_pin_plano_api, name='eliminar_pin_plano_api')`
    - _Requirements: 6.1, 6.2, 6.3_

- [x] 3. Backend: Modificar vista visor_plano_proyecto para inyectar datos
  - [x] 3.1 Extender la vista `visor_plano_proyecto` en `proyectos/views.py`
    - Consultar todos los `PinObservacionProyecto` del plano actual con `select_related('observacion', 'observacion__usuario')`
    - Serializar pines a lista de dicts con: id, x, y, pagina, color, nota, observacion_id, observacion_texto (completo), observacion_estado, observacion_usuario, observacion_fecha
    - Consultar observaciones del proyecto que NO están vinculadas al plano actual: `ObservacionProyecto.objects.filter(proyecto=proyecto).exclude(id__in=pines.values_list('observacion_id', flat=True))`
    - Serializar observaciones disponibles: id, texto (primeros 100 chars), estado
    - Pasar al contexto del template: `pines_json` (json.dumps de pines), `observaciones_disponibles_json` (json.dumps de observaciones)
    - _Requirements: 7.1, 7.2, 7.3_

- [x] 4. Checkpoint - Verificar backend completo
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Frontend: Estructura HTML de la capa de pines y modales
  - [x] 5.1 Agregar la capa de pines y el menú contextual en `proyectos/templates/proyectos/visor_plano_proyecto.html`
    - Insertar un `<div id="pin-layer">` dentro del `#stage` (contenedor del canvas PDF), posicionado absolutamente con las mismas dimensiones
    - Agregar `<div id="context-menu" class="context-menu" style="display:none">` con opción "Agregar Pin de Observación"
    - Usar como referencia la estructura de `core/templates/activos/visor_pdf_plano.html`
    - _Requirements: 2.1, 3.1_

  - [x] 5.2 Agregar el modal de creación de pin en el template
    - Modal con: selector `<select id="select-observacion">` populado con observaciones disponibles, paleta de colores predefinida (6-8 opciones con radio buttons o botones), campo `<textarea id="pin-nota">` para nota opcional, botones "Guardar" y "Cancelar"
    - Incluir bloque de datos JSON inyectados: `<script>const PINES_DATA = {{ pines_json|safe }}; const OBSERVACIONES_DISPONIBLES = {{ observaciones_disponibles_json|safe }};</script>`
    - _Requirements: 3.2, 3.3, 3.4, 7.1, 7.2_

  - [x] 5.3 Agregar el modal de detalle de pin en el template
    - Modal con: texto completo de la observación, badge de estado con color diferenciado (rojo/amarillo/verde/gris), fecha de observación, usuario creador, nota del pin, botón "Eliminar Pin"
    - Diálogo de confirmación de eliminación (puede ser un confirm() nativo o un sub-modal)
    - _Requirements: 4.1, 4.2, 4.3, 5.1, 5.2_

- [x] 6. Frontend: JavaScript para renderizado y posicionamiento de pines
  - [x] 6.1 Implementar la función de renderizado de pines en el template
    - Función `renderizarPines(pagina)` que filtra `PINES_DATA` por página y crea elementos SVG de marcador (gota) para cada pin
    - Posicionar cada pin con `position: absolute`, calculando `left` y `top` a partir de coordenadas almacenadas aplicando escala y traslación del visor: `screenX = x * scale + translateX`, `screenY = y * scale + translateY`
    - Aplicar el color del pin al SVG de marcador
    - Agregar atributo `data-pin-id` y `title` (tooltip con primeros 80 chars de observación)
    - Llamar a `renderizarPines(1)` tras la renderización inicial del PDF
    - _Requirements: 2.1, 2.2, 2.3, 2.5, 7.3_

  - [x] 6.2 Implementar actualización de posición de pines en zoom/pan
    - Escuchar eventos de zoom y pan del visor (hooks existentes en el visor PDF)
    - Recalcular posición de todos los pines visibles cuando cambia scale/translateX/translateY
    - En cambio de página, llamar a `renderizarPines(paginaActual)` para mostrar solo pines de la página activa
    - _Requirements: 2.3, 2.4_

- [x] 7. Frontend: JavaScript para interacción (crear, detalle, eliminar)
  - [x] 7.1 Implementar lógica del menú contextual y creación de pin
    - Listener `contextmenu` en `#pin-layer`: prevenir menú nativo, mostrar `#context-menu` en posición del cursor, almacenar coordenadas relativas al canvas (deshacer transformación: `x = (clientX - translateX) / scale`, `y = (clientY - translateY) / scale`)
    - Al hacer clic en "Agregar Pin de Observación": ocultar menú contextual, abrir modal de creación
    - Al confirmar creación: enviar AJAX POST a `/pines/crear/` con x, y, pagina, observacion_id, color, nota
    - En respuesta exitosa: agregar pin al DOM sin recargar, agregar pin a `PINES_DATA`, remover observación del selector de disponibles
    - En respuesta error: mostrar mensaje en el modal sin cerrarlo
    - Ocultar menú contextual al hacer clic fuera o con Escape
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8_

  - [x] 7.2 Implementar lógica del modal de detalle y eliminación
    - Listener `click` en elementos de pin (`.pin-marker`): abrir modal de detalle con datos de la observación vinculada
    - Popular modal con: observacion_texto, badge de estado con mapeo de colores (ABIERTA→#EF4444, EN_PROCESO→#F59E0B, RESUELTA→#10B981, CERRADA→#6B7280), observacion_fecha, observacion_usuario, nota del pin
    - Al hacer clic en "Eliminar Pin": mostrar confirmación, si acepta enviar AJAX POST a `/pines/<pin_id>/eliminar/`
    - En respuesta exitosa: remover pin del DOM, remover de `PINES_DATA`, agregar observación de vuelta al selector de disponibles, cerrar modal
    - En respuesta error: mostrar mensaje de error en el modal
    - _Requirements: 4.1, 4.2, 4.3, 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 8. Frontend: Estilos CSS para pines, menú y modales
  - [x] 8.1 Agregar estilos CSS para la capa de pines y componentes visuales
    - Estilos para `#pin-layer`: position absolute, pointer-events adecuados, z-index sobre el canvas
    - Estilos para `.pin-marker`: cursor pointer, transición hover, drop-shadow
    - Estilos para `#context-menu`: position fixed, z-index alto, sombra, bordes redondeados
    - Estilos para modales: overlay semitransparente, centrado, responsive
    - Estilos para paleta de colores: botones circulares con borde al seleccionar
    - Estilos para badge de estado: inline-block, border-radius, colores según estado
    - Seguir patrones visuales existentes en el visor de activos
    - _Requirements: 2.2, 4.3_

- [x] 9. Checkpoint - Verificar integración completa
  - Ensure all tests pass, ask the user if questions arise.

- [ ]* 10. Tests: Property-based tests y unit tests
  - [ ]* 10.1 Write property test for Pin data round-trip
    - **Property 1: Pin data round-trip**
    - Usar Hypothesis para generar coordenadas (x, y), página, observación válida, color y nota aleatorios
    - Crear pin vía endpoint POST, luego GET y verificar que todos los campos coinciden
    - **Validates: Requirements 1.1, 6.1**

  - [ ]* 10.2 Write property test for Uniqueness enforcement
    - **Property 2: Uniqueness enforcement**
    - Generar un pin existente, intentar crear otro con mismo (plano, observacion), verificar rechazo y conteo sin cambio
    - **Validates: Requirements 1.4, 3.7**

  - [ ]* 10.3 Write property test for Page filtering
    - **Property 3: Page filtering**
    - Generar pines en múltiples páginas, filtrar por una página y verificar que solo retorna pines de esa página
    - **Validates: Requirements 2.1, 2.4**

  - [ ]* 10.4 Write property test for Available observations filtering
    - **Property 4: Available observations filtering**
    - Generar proyecto con N observaciones y M pines vinculados, verificar que disponibles = N - M
    - **Validates: Requirements 3.2, 7.2**

  - [ ]* 10.5 Write property test for Cross-project validation
    - **Property 5: Cross-project validation**
    - Generar plano de proyecto A y observación de proyecto B, intentar crear pin, verificar rechazo HTTP 400
    - **Validates: Requirements 3.6, 6.5**

  - [ ]* 10.6 Write property test for Tooltip text truncation
    - **Property 6: Tooltip text truncation**
    - Generar textos de observación de longitud variable, verificar que el tooltip es siempre ≤80 chars y coincide con los primeros 80 chars del original
    - **Validates: Requirements 2.5**

  - [ ]* 10.7 Write property test for Pin position invariance under zoom/pan
    - **Property 7: Pin position invariance under zoom/pan**
    - Generar coordenadas base y parámetros de visor (scale, translateX, translateY), verificar fórmula `screenX = x * scale + translateX`
    - **Validates: Requirements 2.3**

  - [ ]* 10.8 Write property test for Estado-to-color badge mapping
    - **Property 8: Estado-to-color badge mapping**
    - Verificar que para cada estado válido, el mapeo retorna siempre el mismo color determinista
    - **Validates: Requirements 4.3**

  - [ ]* 10.9 Write property test for Delete pin preserves observation
    - **Property 9: Delete pin preserves observation**
    - Crear pin, eliminarlo, verificar que la ObservacionProyecto sigue existiendo con todos sus campos intactos
    - **Validates: Requirements 5.5**

  - [ ]* 10.10 Write property test for Authentication enforcement
    - **Property 10: Authentication enforcement**
    - Para cada endpoint, enviar solicitud sin autenticación y verificar respuesta 302 o 403
    - **Validates: Requirements 6.4**

- [x] 11. Checkpoint final - Verificar todo el sistema
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- El template de referencia para la estructura de pines es `core/templates/activos/visor_pdf_plano.html`
- Los datos iniciales se inyectan como JSON en el template (no AJAX) para la carga inicial, siguiendo el patrón del proyecto
- Las coordenadas se almacenan en píxeles absolutos del viewport base del PDF

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["2.1", "2.2", "2.3", "2.4"] },
    { "id": 3, "tasks": ["3.1"] },
    { "id": 4, "tasks": ["5.1", "5.2", "5.3"] },
    { "id": 5, "tasks": ["6.1", "8.1"] },
    { "id": 6, "tasks": ["6.2", "7.1", "7.2"] },
    { "id": 7, "tasks": ["10.1", "10.2", "10.3", "10.4", "10.5", "10.6", "10.7", "10.8", "10.9", "10.10"] }
  ]
}
```
