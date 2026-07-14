# Implementation Plan: Fotos Pin Observación

## Overview

Implementar la funcionalidad de adjuntar, visualizar y eliminar fotografías en los pines de observación del visor de planos PDF. Se crea el modelo `FotoPinObservacion` siguiendo el patrón de `FotoAviso`, dos endpoints API (subir y eliminar), se extiende la vista existente para inyectar fotos en `pines_json`, y se implementa en frontend la grilla de miniaturas, lightbox, y gestión de fotos tanto en el modal de detalle como en el de creación.

## Tasks

- [ ] 1. Backend: Modelo y migración
  - [ ] 1.1 Crear modelo `FotoPinObservacion` en `proyectos/models.py`
    - Definir FK a `PinObservacionProyecto` con `on_delete=CASCADE` y `related_name='fotos'`
    - Campo `imagen = ImageField(upload_to='proyectos/fotos_pines/')`
    - Campo `creado_en = DateTimeField(auto_now_add=True)`
    - Override de `save()` que aplica `compress_image` a la imagen antes de guardar
    - Importar `compress_image` desde `core.image_utils`
    - Meta: `ordering = ['creado_en']`, verbose_name apropiado
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [ ] 1.2 Generar y aplicar migración
    - Ejecutar `python manage.py makemigrations proyectos`
    - Ejecutar `python manage.py migrate`
    - _Requirements: 1.1_

- [ ] 2. Backend: Endpoints API para fotos
  - [ ] 2.1 Implementar endpoint `subir_fotos_pin_api` en `proyectos/views.py`
    - Decorar con `@staff_member_required`
    - Validar que el pin pertenece al plano y proyecto indicados en la URL (`get_object_or_404`)
    - Obtener archivos con `request.FILES.getlist('fotos')`
    - Validar límite: contar fotos actuales del pin, rechazar con HTTP 400 si `existentes + nuevas > 5`
    - Validar MIME de cada archivo (`image/jpeg`, `image/png`), rechazar con HTTP 400 si inválido
    - Guardar cada foto como `FotoPinObservacion(pin=pin, imagen=archivo)` y llamar `.save()`
    - Responder HTTP 200 con JSON `{status: 'success', fotos: [{id, url}, ...]}`
    - _Requirements: 7.1, 7.3, 7.4, 7.7, 8.1, 8.2, 8.3, 8.4_

  - [ ] 2.2 Implementar endpoint `eliminar_foto_pin_api` en `proyectos/views.py`
    - Decorar con `@staff_member_required`
    - Validar que pin y foto pertenecen al plano/proyecto indicados en la URL
    - Obtener la foto con `get_object_or_404(FotoPinObservacion, pk=foto_id, pin=pin)`
    - Eliminar la foto y responder HTTP 200 con `{status: 'success'}`
    - _Requirements: 7.2, 7.5, 7.6, 8.2, 8.3_

  - [ ] 2.3 Registrar URLs de los endpoints en `proyectos/urls.py`
    - `path('proyecto/<int:pk>/planos/<int:plano_id>/pines/<int:pin_id>/fotos/subir/', views.subir_fotos_pin_api, name='subir_fotos_pin_api')`
    - `path('proyecto/<int:pk>/planos/<int:plano_id>/pines/<int:pin_id>/fotos/<int:foto_id>/eliminar/', views.eliminar_foto_pin_api, name='eliminar_foto_pin_api')`
    - _Requirements: 7.1, 7.2_

- [ ] 3. Backend: Extender vista del visor para inyectar fotos
  - [ ] 3.1 Modificar la serialización de `pines_data` en `visor_plano_proyecto`
    - Usar `prefetch_related('fotos')` en la consulta de pines para optimizar queries
    - Para cada pin, agregar campo `'fotos': [{'id': f.id, 'url': f.imagen.url} for f in pin.fotos.all()]`
    - _Requirements: 4.5_

- [ ] 4. Checkpoint - Verificar backend
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Frontend: Grilla de miniaturas y gestión de fotos en modal detalle
  - [ ] 5.1 Agregar HTML de la sección de fotos en `#modal-detalle-pin`
    - Contenedor `#detail-fotos-section` con label "Fotos"
    - Div `#detail-fotos-grid` con clase `fotos-grid` para la grilla
    - Mensaje `#fotos-limit-msg` (oculto por defecto) indicando máximo alcanzado
    - Botón `#btn-agregar-fotos` para disparar la selección de archivos
    - Input file oculto `#input-fotos-detalle` con `multiple accept="image/jpeg,image/png"`
    - _Requirements: 3.1, 3.2, 3.3, 4.1, 4.4_

  - [ ] 5.2 Agregar CSS para la grilla de miniaturas
    - `.fotos-grid`: display grid, 3 columnas, gap 6px
    - `.foto-thumb`: aspect-ratio 1, border-radius 6px, overflow hidden, cursor pointer, posición relativa
    - `.foto-thumb img`: width/height 100%, object-fit cover
    - `.btn-delete-foto`: posición absoluta top-right, fondo oscuro, ícono rojo, oculto por defecto, visible en hover
    - _Requirements: 4.2, 4.3_

  - [ ] 5.3 Implementar JavaScript para renderizar grilla y gestionar fotos en modal detalle
    - Función `renderFotosGrid(pinData)` que construye miniaturas con botón de eliminar
    - Al abrir modal detalle: mostrar/ocultar `#detail-fotos-section` según si hay fotos
    - Gestionar visibilidad de `#btn-agregar-fotos` vs `#fotos-limit-msg` según conteo de fotos (límite 5)
    - Listener en `#btn-agregar-fotos` que dispara clic en `#input-fotos-detalle`
    - Listener en `#input-fotos-detalle` change: validar archivos, construir FormData, enviar fetch POST con CSRF a endpoint de subida
    - En respuesta exitosa: agregar nuevas fotos al array del pin en `PINES_DATA`, re-renderizar grilla
    - En error: mostrar mensaje de error dentro del modal
    - _Requirements: 3.4, 3.5, 3.6, 3.7, 6.5_

  - [ ] 5.4 Implementar eliminación de fotos desde la grilla
    - Listener delegado en `.btn-delete-foto`: solicitar confirmación con `confirm()`
    - En confirmación: enviar fetch POST al endpoint de eliminación con CSRF
    - En éxito: remover miniatura del DOM, actualizar array de fotos del pin en `PINES_DATA`
    - Si fotos quedan < 5: mostrar `#btn-agregar-fotos` de nuevo
    - Si fotos quedan 0: ocultar `#detail-fotos-section`
    - En error: mostrar mensaje de error, mantener miniatura visible
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

- [ ] 6. Frontend: Lightbox para visualización a tamaño completo
  - [ ] 6.1 Agregar HTML y CSS del lightbox
    - Overlay `#lightbox-overlay` con `position: fixed`, fondo `rgba(0,0,0,0.85)`, z-index alto
    - Botón de cierre `#lightbox-close` en esquina superior derecha
    - Imagen `#lightbox-img` centrada con max-width/max-height 90vw/90vh
    - Botones de navegación `#lightbox-prev` y `#lightbox-next` posicionados a los lados
    - CSS para estilos de overlay, imagen, botones de cierre y navegación
    - _Requirements: 5.1, 5.2, 5.3, 5.6_

  - [ ] 6.2 Implementar JavaScript del lightbox
    - Variable `lightboxFotos` (array actual) y `lightboxIndex` (índice actual)
    - Función `openLightbox(fotos, index)` que muestra el overlay con la foto indicada
    - Función `closeLightbox()` que oculta el overlay
    - Navegación: prev/next actualizan `lightboxIndex` y cambian `src` de la imagen
    - Ocultar flechas si solo hay una foto
    - Listener clic en miniatura: abrir lightbox con array de fotos del pin y el índice correspondiente
    - Listener clic en fondo oscuro: cerrar lightbox
    - Listener tecla Escape: cerrar lightbox
    - _Requirements: 5.1, 5.4, 5.5, 5.6_

- [ ] 7. Frontend: Fotos en modal de creación de pin
  - [ ] 7.1 Agregar campo de fotos en `#modal-crear-pin`
    - Sección `#crear-fotos-section` con label "Fotos (opcional, máx. 5)"
    - Input file `#input-fotos-crear` con `multiple accept="image/jpeg,image/png"`
    - Div `#crear-fotos-preview` con clase `fotos-grid` para previews
    - Div `#crear-fotos-error` para mensajes de error
    - _Requirements: 2.1, 2.2_

  - [ ] 7.2 Implementar JavaScript para gestión de fotos en creación
    - Listener change en `#input-fotos-crear`: validar tipo (JPG/PNG) y cantidad (máx 5)
    - Mostrar previews como miniaturas usando `FileReader` y `URL.createObjectURL`
    - Permitir remover fotos de la selección antes de guardar
    - Si archivos inválidos: mostrar error en `#crear-fotos-error`, rechazar archivos inválidos
    - Si más de 5: mostrar error indicando límite
    - _Requirements: 2.3, 2.4_

  - [ ] 7.3 Integrar fotos en el flujo de guardado del pin
    - Modificar la función de guardado del pin para usar `FormData` con los datos del pin + archivos de fotos
    - Enviar como `multipart/form-data` en vez de JSON cuando hay fotos adjuntas
    - Si el pin se crea exitosamente: subir fotos al endpoint `subir_fotos_pin_api` con el pin_id recibido
    - Si la subida de fotos falla: mantener el pin creado, mostrar aviso al usuario de que las fotos no se subieron
    - Limpiar el input y previews al cerrar o completar exitosamente
    - _Requirements: 2.5, 2.6_

- [ ] 8. Checkpoint - Verificar integración frontend completa
  - Ensure all tests pass, ask the user if questions arise.

- [ ]* 9. Tests: Property-based tests con Hypothesis
  - [ ]* 9.1 Write property test for photo upload round-trip
    - **Property 1: Photo upload round-trip**
    - Generar imágenes válidas (JPG/PNG) con Hypothesis y subir al endpoint
    - Verificar respuesta 200 con `id` y `url` bajo `proyectos/fotos_pines/`
    - Verificar que consultando las fotos del pin aparece el nuevo registro
    - **Validates: Requirements 1.1, 1.2, 7.7**

  - [ ]* 9.2 Write property test for image compression invariant
    - **Property 2: Image compression invariant**
    - Generar imágenes de ancho aleatorio (500-4000px) y guardar como FotoPinObservacion
    - Verificar que la imagen almacenada tiene width <= 1024 y formato JPEG
    - **Validates: Requirements 1.3**

  - [ ]* 9.3 Write property test for cascade deletion
    - **Property 3: Cascade deletion of photos**
    - Generar pins con N fotos (0-5) y eliminar el pin
    - Verificar que FotoPinObservacion.objects.filter(pin=pin) retorna vacío
    - **Validates: Requirements 1.4**

  - [ ]* 9.4 Write property test for maximum 5 photos enforcement
    - **Property 4: Maximum 5 photos enforcement**
    - Generar K fotos existentes (0-5) e intentar subir N archivos adicionales
    - Verificar: aceptar si K+N <= 5, rechazar con 400 si K+N > 5
    - **Validates: Requirements 1.5, 7.3, 3.3, 3.4, 6.5**

  - [ ]* 9.5 Write property test for MIME type validation
    - **Property 5: MIME type validation rejects non-image files**
    - Generar archivos con content_type aleatorio no-JPG/PNG
    - Verificar que el endpoint rechaza con HTTP 400
    - **Validates: Requirements 7.4, 8.1, 8.4**

  - [ ]* 9.6 Write property test for authentication enforcement
    - **Property 6: Authentication enforcement**
    - Generar requests sin autenticación de staff a ambos endpoints
    - Verificar respuesta HTTP 302 (redirect a login)
    - **Validates: Requirements 7.5, 8.2**

  - [ ]* 9.7 Write property test for pin-project ownership validation
    - **Property 7: Pin-project ownership validation**
    - Generar solicitudes con URLs que referencian proyecto diferente al del pin
    - Verificar respuesta HTTP 404
    - **Validates: Requirements 8.3**

  - [ ]* 9.8 Write property test for photo ordering
    - **Property 8: Photo ordering by creation date**
    - Crear pin con múltiples fotos en distintos momentos
    - Verificar que el queryset y pines_json las devuelven en orden ascendente por `creado_en`
    - **Validates: Requirements 4.5**

- [ ] 10. Checkpoint final - Verificar todo el sistema
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate correctness properties defined in the design document
- Se sigue el patrón de `FotoAviso` en `mantenimiento/models.py` como referencia para el modelo
- `compress_image` se importa desde `core.image_utils` (mismos parámetros por defecto: max_width=1024, quality=70)
- Las fotos se inyectan en `pines_json` durante la carga de la vista, evitando AJAX extras
- Los modales `#modal-detalle-pin` y `#modal-crear-pin` ya existen y se extienden con HTML/JS adicional
- Se usa Hypothesis (Python) para todos los property-based tests del backend

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["2.1", "2.2", "2.3"] },
    { "id": 3, "tasks": ["3.1"] },
    { "id": 4, "tasks": ["5.1", "5.2", "6.1", "7.1"] },
    { "id": 5, "tasks": ["5.3", "5.4", "6.2", "7.2"] },
    { "id": 6, "tasks": ["7.3"] },
    { "id": 7, "tasks": ["9.1", "9.2", "9.3", "9.4", "9.5", "9.6", "9.7", "9.8"] }
  ]
}
```
