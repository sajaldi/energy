# Implementation Plan: Áreas en Plano de Proyecto

## Overview

Implementar un sistema de áreas rectangulares sobre planos PDF de proyecto. Se crea el modelo `AreaPlanoProyecto` en la app `proyectos`, se implementan 3 endpoints API (crear, editar, eliminar), se extiende la vista `visor_plano_proyecto` para inyectar `areas_json`, y se agrega al template la capa de áreas (`#area-layer`), panel lateral, modo de creación por arrastre, edición por doble clic, y contención dinámica pin-área. El sistema sigue el patrón Django + JavaScript vanilla existente.

## Tasks

- [ ] 1. Backend: Modelo AreaPlanoProyecto y migración
  - [ ] 1.1 Crear el modelo `AreaPlanoProyecto` en `proyectos/models.py`
    - `ColorField` ya está importado en models.py
    - Definir modelo con campos: `plano` (FK a PlanoProyecto, CASCADE, related_name='areas'), `nombre` (CharField max_length=100), `color` (ColorField default='#3B82F6'), `x1` (FloatField), `y1` (FloatField), `x2` (FloatField), `y2` (FloatField), `pagina` (PositiveIntegerField default=1), `creado_en` (DateTimeField auto_now_add=True)
    - Configurar `class Meta`: ordering=['creado_en'], verbose_name="Área de Plano de Proyecto", verbose_name_plural="Áreas de Plano de Proyecto"
    - Implementar `__str__` retornando `f"{self.nombre} - {self.plano.titulo} (p.{self.pagina})"`
    - Implementar método `contiene_punto(self, px, py)` que retorna True si el punto está dentro del rectángulo
    - Implementar método `obtener_pines(self)` que retorna queryset de PinObservacionProyecto contenidos en el área (misma página, coordenadas dentro del rectángulo)
    - _Requirements: 7.1, 5.1, 5.3_

  - [ ] 1.2 Generar y aplicar la migración de Django
    - Ejecutar `python manage.py makemigrations proyectos`
    - Verificar migración creada en `proyectos/migrations/`
    - Ejecutar `python manage.py migrate`
    - _Requirements: 7.1_

- [ ] 2. Backend: Endpoints API de áreas
  - [ ] 2.1 Implementar `crear_area_plano_api` en `proyectos/views.py`
    - Decorador `@staff_member_required`
    - Aceptar solo método POST, retornar 405 para otros métodos
    - Obtener proyecto por `pk` y plano por `plano_id` con get_object_or_404, validar que plano pertenece al proyecto (HTTP 400 si no)
    - Parsear JSON del body: x1, y1, x2, y2, pagina, nombre, color
    - Normalizar coordenadas: x1=min(xa,xb), y1=min(ya,yb), x2=max(xa,xb), y2=max(ya,yb)
    - Validar tamaño mínimo: (x2-x1) >= 10 y (y2-y1) >= 10, retornar HTTP 400 con mensaje si falla
    - Validar nombre no vacío ni solo espacios, retornar HTTP 400 si falla
    - Crear `AreaPlanoProyecto` con los datos normalizados
    - Retornar JSON: `{"status": "success", "area": {id, nombre, color, x1, y1, x2, y2, pagina}}`
    - _Requirements: 1.4, 1.5, 1.7, 7.3, 7.6, 8.1, 8.3_

  - [ ] 2.2 Implementar `editar_area_plano_api` en `proyectos/views.py`
    - Decorador `@staff_member_required`
    - Aceptar solo método POST, retornar 405 para otros métodos
    - Obtener proyecto, plano y área con get_object_or_404, validar cadena de pertenencia (área pertenece a plano, plano pertenece a proyecto)
    - Parsear JSON del body: nombre, color
    - Validar nombre no vacío ni solo espacios, retornar HTTP 400 si falla
    - Actualizar nombre y color del área, guardar
    - Retornar JSON: `{"status": "success", "area": {id, nombre, color, x1, y1, x2, y2, pagina}}`
    - _Requirements: 3.2, 3.3, 3.4, 7.4, 8.1, 8.3_

  - [ ] 2.3 Implementar `eliminar_area_plano_api` en `proyectos/views.py`
    - Decorador `@staff_member_required`
    - Aceptar solo método POST, retornar 405 para otros métodos
    - Obtener proyecto, plano y área con get_object_or_404, validar cadena de pertenencia
    - Eliminar el área (solo AreaPlanoProyecto, los pines NO se afectan por contención dinámica)
    - Retornar JSON: `{"status": "success"}`
    - _Requirements: 4.3, 4.4, 4.6, 7.5, 8.1, 8.3_

  - [ ] 2.4 Registrar las URLs de los endpoints en `proyectos/urls.py`
    - Agregar `path('proyecto/<int:pk>/planos/<int:plano_id>/areas/crear/', views.crear_area_plano_api, name='crear_area_plano_api')`
    - Agregar `path('proyecto/<int:pk>/planos/<int:plano_id>/areas/<int:area_id>/editar/', views.editar_area_plano_api, name='editar_area_plano_api')`
    - Agregar `path('proyecto/<int:pk>/planos/<int:plano_id>/areas/<int:area_id>/eliminar/', views.eliminar_area_plano_api, name='eliminar_area_plano_api')`
    - _Requirements: 7.6_

- [ ] 3. Backend: Extender vista visor_plano_proyecto para inyectar áreas
  - [ ] 3.1 Extender la vista `visor_plano_proyecto` en `proyectos/views.py`
    - Consultar `AreaPlanoProyecto.objects.filter(plano=plano)`
    - Serializar áreas a lista de dicts: id, nombre, color, x1, y1, x2, y2, pagina
    - Pasar al contexto del template: `areas_json` (json.dumps de areas_data, ensure_ascii=False)
    - _Requirements: 7.2_

- [ ] 4. Checkpoint - Verificar backend completo
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Frontend: Estructura HTML de capa de áreas y panel lateral
  - [ ] 5.1 Agregar `#area-layer` y panel lateral al template `visor_plano_proyecto.html`
    - Insertar `<div id="area-layer"></div>` dentro de `#stage`, ANTES de `#pin-layer` (para que pines queden encima en z-index)
    - Agregar bloque de datos JSON: `<script>const AREAS_DATA = {{ areas_json|safe }};</script>`
    - Agregar panel lateral `#areas-panel` en la sidebar junto al panel de pines: header con título "▢ Áreas" y badge de conteo, contenedor `#areas-list` para items
    - Agregar estructura del formulario inline de creación de área (nombre + color picker, botones Guardar/Cancelar)
    - Agregar estructura del formulario inline de edición de área (nombre + color picker pre-poblados, botones Guardar/Cancelar)
    - _Requirements: 2.1, 6.1, 1.3, 3.1_

- [ ] 6. Frontend: JavaScript para renderizado y gestión de áreas
  - [ ] 6.1 Implementar renderizado de áreas en el template
    - Función `renderizarAreas(pagina)` que filtra `AREAS_DATA` por página y crea un `<div class="area-rect">` por cada área
    - Posicionar cada div con `position: absolute`, calculando left/top/width/height aplicando escala y traslación del visor: `left = x1 * scale + translateX`, `top = y1 * scale + translateY`, `width = (x2-x1) * scale`, `height = (y2-y1) * scale`
    - Aplicar background-color con rgba (opacidad 0.15) y border con rgba (opacidad 0.7) usando el color del área
    - Agregar `data-area-id` y `title` (nombre del área como tooltip)
    - Llamar a `renderizarAreas(1)` tras la renderización inicial del PDF
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 9.1_

  - [ ] 6.2 Implementar actualización de posición de áreas en zoom/pan
    - Escuchar eventos de zoom y pan del visor (hooks existentes)
    - Recalcular posición y tamaño de todas las áreas visibles cuando cambia scale/translateX/translateY
    - En cambio de página, llamar a `renderizarAreas(paginaActual)` para mostrar solo áreas de la página activa
    - _Requirements: 2.3, 2.5, 9.1_

  - [ ] 6.3 Implementar modo de creación de área por arrastre
    - Agregar opción "Agregar Área" al menú contextual existente del visor
    - Al seleccionar "Agregar Área": activar `areaCreationMode = true`, cambiar cursor a `crosshair`
    - En mousedown: registrar punto inicial en coordenadas viewport base (deshacer transformación)
    - En mousemove: dibujar rectángulo preview con borde punteado desde punto inicial al cursor actual
    - En mouseup: mostrar formulario de creación con los campos nombre y color
    - Escape cancela el modo de creación y vuelve al modo normal
    - _Requirements: 1.1, 1.2, 1.3, 1.6_

  - [ ] 6.4 Implementar lógica de creación de área (submit del formulario)
    - Al confirmar el formulario de creación: enviar AJAX POST a `/areas/crear/` con x1, y1, x2, y2, pagina, nombre, color
    - En respuesta exitosa: agregar área al DOM y a `AREAS_DATA`, actualizar panel lateral, cerrar formulario
    - En respuesta error (área muy pequeña, nombre vacío): mostrar mensaje en formulario sin cerrarlo
    - Validar mínimo 10x10 px en frontend antes de enviar (feedback inmediato)
    - _Requirements: 1.4, 1.5, 1.7, 6.3_

  - [ ] 6.5 Implementar edición de área (doble clic)
    - Listener `dblclick` en elementos `.area-rect`: abrir formulario de edición pre-poblado con nombre y color actuales
    - Al confirmar: enviar AJAX POST a `/areas/<id>/editar/` con nombre y color nuevos
    - En respuesta exitosa: actualizar el div del área (color, tooltip), actualizar `AREAS_DATA`, actualizar panel lateral
    - En respuesta error: mostrar mensaje en formulario sin cerrarlo
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [ ] 6.6 Implementar eliminación de área (menú contextual)
    - Listener `contextmenu` en elementos `.area-rect`: mostrar menú contextual con opción "Eliminar Área"
    - Al seleccionar "Eliminar Área": mostrar confirmación con el nombre del área
    - Al confirmar: enviar AJAX POST a `/areas/<id>/eliminar/`
    - En respuesta exitosa: remover div del DOM, remover de `AREAS_DATA`, actualizar panel lateral
    - Prevenir propagación del contextmenu al `#pin-layer`
    - _Requirements: 4.1, 4.2, 4.3, 4.5, 4.6_

  - [ ] 6.7 Implementar panel lateral de áreas con contención dinámica
    - Función `actualizarPanelAreas()` que renderiza la lista de áreas de la página actual
    - Cada item del panel: indicador circular de color, nombre, conteo de pines (calculado con `getPinesEnArea`)
    - Click en item del panel centra el visor en el área correspondiente
    - Función `getPinesEnArea(area)` que filtra PINES_DATA por contención geométrica y misma página
    - Actualizar panel al crear/editar/eliminar áreas y al cambiar de página
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 5.1, 5.4_

  - [ ] 6.8 Implementar highlight de pines al interactuar con área
    - Al hacer hover sobre un área (div o item del panel), destacar visualmente los pines contenidos (agregar clase CSS)
    - Al quitar hover, restaurar estilo normal de los pines
    - Función `highlightPinesEnArea(area)` y `clearHighlightPines()`
    - _Requirements: 5.5_

- [ ] 7. Frontend: Estilos CSS para áreas y panel
  - [ ] 7.1 Agregar estilos CSS para la capa de áreas y componentes
    - Estilos para `#area-layer`: position absolute, pointer-events none en contenedor, pointer-events auto en `.area-rect`
    - Estilos para `.area-rect`: cursor default, transición hover (opacidad sube a 0.25)
    - Estilos para `.area-rect` con tooltip (title attr)
    - Estilos para preview de arrastre: borde punteado, sin fill
    - Estilos para `#areas-panel`: mismos patrones del panel de pines existente
    - Estilos para items del panel: flexbox, indicador circular de color, nombre truncado, badge de conteo
    - Estilos para formularios inline de creación/edición
    - Estilos para highlight de pines contenidos
    - _Requirements: 2.2, 2.4, 6.1_

- [ ] 8. Checkpoint - Verificar integración completa
  - Ensure all tests pass, ask the user if questions arise.

- [ ]* 9. Tests: Property-based tests
  - [ ]* 9.1 Write property test for coordinate normalization on creation
    - **Property 1: Coordinate normalization on creation**
    - Usar Hypothesis para generar pares de coordenadas (xa, ya, xb, yb) donde el rectángulo resultante tiene ancho y alto >= 10
    - Enviar a endpoint crear y verificar que el área persistida tiene x1=min(xa,xb), y1=min(ya,yb), x2=max(xa,xb), y2=max(ya,yb)
    - **Validates: Requirements 1.5, 1.7**

  - [ ]* 9.2 Write property test for page filtering consistency
    - **Property 2: Page filtering consistency**
    - Generar áreas distribuidas en múltiples páginas, verificar que al filtrar por una página solo se obtienen áreas de esa página (tanto en visor como en panel)
    - **Validates: Requirements 2.1, 2.5, 6.5, 9.1**

  - [ ]* 9.3 Write property test for area position invariance under zoom/pan
    - **Property 3: Area position invariance under zoom/pan**
    - Generar coordenadas base y parámetros de visor (scale, translateX, translateY), verificar fórmula: screenLeft = x1*scale+translateX, screenTop = y1*scale+translateY, screenWidth = (x2-x1)*scale, screenHeight = (y2-y1)*scale
    - **Validates: Requirements 2.3**

  - [ ]* 9.4 Write property test for area update persists and validates name
    - **Property 4: Area update persists and validates name**
    - Generar nombres válidos (no vacíos) y colores, enviar a endpoint editar, verificar persistencia. Generar nombres vacíos/espacios, verificar rechazo HTTP 400 y área sin cambios
    - **Validates: Requirements 3.3, 3.4**

  - [ ]* 9.5 Write property test for area deletion preserves all pins
    - **Property 5: Area deletion preserves all pins**
    - Crear área con pines contenidos, eliminar área, verificar que todos los PinObservacionProyecto siguen intactos en BD
    - **Validates: Requirements 4.4, 4.6**

  - [ ]* 9.6 Write property test for dynamic pin-area containment
    - **Property 6: Dynamic pin-area containment**
    - Generar pines con coordenadas aleatorias y áreas con rectángulos aleatorios, verificar que la función de contención retorna True si y solo si P==Q AND x1<=px<=x2 AND y1<=py<=y2
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 9.2**

  - [ ]* 9.7 Write property test for ownership validation across endpoints
    - **Property 7: Ownership validation across endpoints**
    - Generar requests donde plano no pertenece al proyecto o área no pertenece al plano, verificar rechazo HTTP 400/404
    - **Validates: Requirements 7.3, 7.4, 7.5**

  - [ ]* 9.8 Write property test for authentication enforcement
    - **Property 8: Authentication enforcement**
    - Para cada endpoint de áreas, enviar request sin autenticación, verificar HTTP 302 redirect a login
    - **Validates: Requirements 8.1, 8.2**

  - [ ]* 9.9 Write property test for HTTP method validation
    - **Property 9: HTTP method validation**
    - Para cada endpoint, enviar request con métodos GET/PUT/DELETE/PATCH, verificar HTTP 405
    - **Validates: Requirements 8.3**

- [ ] 10. Checkpoint final - Verificar todo el sistema
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- `ColorField` ya está importado en `proyectos/models.py`, no hace falta importarlo de nuevo
- El visor ya tiene `#stage` con canvas + `#pin-layer` dentro, menú contextual, panel de pines, zoom/pan
- Las áreas se inyectan como JSON en el template (igual que `pines_json`), no AJAX en carga
- La relación pin-área es computada dinámicamente (sin FK), los pines nunca se afectan al eliminar áreas
- Las coordenadas se normalizan (x1<=x2, y1<=y2) al persistir, independientemente de la dirección del arrastre

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["2.1", "2.2", "2.3", "2.4"] },
    { "id": 3, "tasks": ["3.1"] },
    { "id": 4, "tasks": ["5.1"] },
    { "id": 5, "tasks": ["6.1", "6.3", "7.1"] },
    { "id": 6, "tasks": ["6.2", "6.4", "6.5", "6.6"] },
    { "id": 7, "tasks": ["6.7", "6.8"] },
    { "id": 8, "tasks": ["9.1", "9.2", "9.3", "9.4", "9.5", "9.6", "9.7", "9.8", "9.9"] }
  ]
}
```
