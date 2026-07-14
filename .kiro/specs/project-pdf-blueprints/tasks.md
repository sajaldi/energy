# Implementation Plan: Planos PDF en Proyecto

## Overview

Implementar la funcionalidad de carga, listado, visualización y eliminación de planos PDF asociados a un proyecto. Se crea un nuevo modelo `PlanoProyecto` en la app `proyectos`, se agregan 5 endpoints API REST, se modifica el template `proyecto_detalle_fiori.html` para incluir la pestaña "Planos PDF" con dropzone y tabla, y se crea un visor PDF standalone basado en el patrón existente de `core/templates/activos/visor_pdf_plano.html`.

## Tasks

- [x] 1. Backend: Modelo PlanoProyecto y migración
  - [x] 1.1 Crear el modelo `PlanoProyecto` en `proyectos/models.py`
    - Importar `from core.storage import MinIOStorage` e instanciar `minio_storage = MinIOStorage()`
    - Definir modelo con campos: `proyecto` (FK a Proyecto, CASCADE, related_name='planos_pdf'), `titulo` (CharField max_length=200), `descripcion` (TextField blank=True), `archivo` (FileField upload_to='proyectos/planos/', storage=minio_storage, max_length=500), `subido_por` (FK a User, SET_NULL, null=True), `fecha_carga` (DateTimeField auto_now_add=True)
    - Configurar `class Meta`: verbose_name, verbose_name_plural, ordering=['-fecha_carga']
    - Implementar `__str__` retornando `f"{self.proyecto.codigo} - {self.titulo}"`
    - Conectar señal `post_delete` para eliminar archivo de MinIO al borrar el registro
    - _Requirements: 6.1, 6.2, 6.3_

  - [x] 1.2 Generar y aplicar la migración de Django
    - Ejecutar `python manage.py makemigrations proyectos`
    - Verificar que la migración se creó correctamente en `proyectos/migrations/`
    - Ejecutar `python manage.py migrate`
    - _Requirements: 6.1_

- [x] 2. Backend: Endpoints API de planos
  - [x] 2.1 Implementar `listar_planos_api` en `proyectos/views.py`
    - Decoradores: `@csrf_exempt`, `@staff_member_required`
    - Aceptar solo método GET, retornar 405 para otros métodos
    - Obtener proyecto por `pk` con get_object_or_404
    - Leer parámetro `page` (default 1), paginar con 20 items por página usando `Paginator`
    - Serializar cada plano: id, titulo, descripcion, fecha_carga (ISO), usuario_nombre (subido_por.get_full_name() o username), url_archivo (reverse a download)
    - Retornar JSON: `{status: "success", data: {planos: [...], total, page, total_pages}}`
    - _Requirements: 3.1, 3.3, 7.2, 7.5, 7.6_

  - [x] 2.2 Implementar `upload_plano_api` en `proyectos/views.py`
    - Decoradores: `@csrf_exempt`, `@staff_member_required`
    - Aceptar solo método POST, retornar 405 para otros
    - Obtener proyecto por `pk` con get_object_or_404
    - Validar que `request.FILES` contiene 'archivo'
    - Validar extensión `.pdf` y content-type `application/pdf`
    - Validar tamaño máximo 50 MB (50 * 1024 * 1024 bytes)
    - Validar `titulo` (required, 1-200 chars) y `descripcion` (optional, max 500 chars)
    - Crear registro `PlanoProyecto` con archivo, titulo, descripcion, proyecto, subido_por=request.user
    - Envolver en try/except para capturar errores de MinIO al guardar
    - Retornar JSON: `{status: "success", message: "Plano cargado exitosamente", data: {id, titulo, fecha_carga}}`
    - _Requirements: 2.2, 2.3, 2.4, 2.6, 2.7, 6.4, 6.5, 7.1, 7.5_

  - [x] 2.3 Implementar `delete_plano_api` en `proyectos/views.py`
    - Decoradores: `@csrf_exempt`, `@staff_member_required`
    - Aceptar solo método DELETE, retornar 405 para otros
    - Obtener proyecto y plano con get_object_or_404 (filtrar plano por proyecto_id para seguridad)
    - Eliminar el registro (la señal post_delete se encarga de borrar el archivo en MinIO)
    - Envolver en try/except para capturar errores
    - Retornar JSON: `{status: "success", message: "Plano eliminado exitosamente"}`
    - _Requirements: 5.3, 7.3, 7.5_

  - [x] 2.4 Implementar `download_plano` en `proyectos/views.py`
    - Decorador: `@staff_member_required`
    - Obtener proyecto y plano con get_object_or_404
    - Verificar que el archivo existe en storage (`plano.archivo.storage.exists(plano.archivo.name)`)
    - Retornar FileResponse/HttpResponse con Content-Disposition: `attachment; filename="{titulo}.pdf"`
    - Si el archivo no existe, retornar 404 con JSON error
    - _Requirements: 4.3, 4.4_

  - [x] 2.5 Implementar `visor_plano_proyecto` en `proyectos/views.py`
    - Decorador: `@staff_member_required`
    - Obtener proyecto y plano con get_object_or_404
    - Generar URL del archivo (presigned URL de MinIO o URL directa)
    - Renderizar template `proyectos/visor_plano_proyecto.html` con contexto: plano, proyecto, pdf_url
    - Si el archivo no existe, renderizar template con flag de error
    - _Requirements: 4.1, 4.2, 4.4_

  - [x] 2.6 Registrar las URLs de los 5 endpoints en `proyectos/urls.py`
    - `path('proyecto/<int:pk>/planos/', views.listar_planos_api, name='listar_planos_api')`
    - `path('proyecto/<int:pk>/planos/upload/', views.upload_plano_api, name='upload_plano_api')`
    - `path('proyecto/<int:pk>/planos/<int:plano_id>/delete/', views.delete_plano_api, name='delete_plano_api')`
    - `path('proyecto/<int:pk>/planos/<int:plano_id>/download/', views.download_plano, name='download_plano')`
    - `path('proyecto/<int:pk>/planos/<int:plano_id>/visor/', views.visor_plano_proyecto, name='visor_plano_proyecto')`
    - _Requirements: 7.1, 7.2, 7.3_

- [x] 3. Checkpoint - Verificar modelo y endpoints
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Frontend: Pestaña "Planos PDF" en la vista de detalle
  - [x] 4.1 Agregar la pestaña "Planos PDF" en la barra de tabs de `proyectos/templates/proyectos/proyecto_detalle_fiori.html`
    - Insertar `<div class="sap-tab" data-target="planos-pdf">Planos PDF</div>` después de `data-target="documentos"` (Documentos vinculados) y antes de `data-target="visor"` (Órdenes de Trabajo)
    - La línea exacta es después de la línea 441 (después del tab "Documentos vinculados")
    - _Requirements: 1.1, 1.3_

  - [x] 4.2 Agregar la sección HTML `<section id="planos-pdf">` en `proyecto_detalle_fiori.html`
    - Área de dropzone con border dashed, ícono de upload, texto "Arrastra archivos PDF aquí o haz clic para seleccionar", input file hidden
    - Formulario inline con campos: título (input text, required, max 200) y descripción (textarea, opcional, max 500)
    - Tabla con columnas: Título, Fecha de carga (dd/mm/aaaa), Subido por, Acciones (Ver, Descargar, Eliminar)
    - Estado vacío: mensaje "No hay planos asociados a este proyecto" con botón "Subir primer plano"
    - Controles de paginación (anterior/siguiente con indicador de página)
    - _Requirements: 1.1, 1.4, 2.1, 3.1, 3.2, 3.3_

  - [x] 4.3 Agregar estilos CSS para la sección de planos en el bloque `<style>` de `proyecto_detalle_fiori.html`
    - Estilos para `.planos-dropzone`: border dashed 2px, border-radius, padding, text-align center, cursor pointer, transiciones hover
    - Estilos para `.planos-dropzone.drag-over`: border-color primario, background highlight
    - Estilos para la tabla de planos: estilo consistente con las demás tablas del template
    - Estilos para botones de acción: colores para Ver (azul), Descargar (verde), Eliminar (rojo)
    - Estilos para el empty state y la paginación
    - _Requirements: 1.2, 2.1_

- [x] 5. Frontend: Módulo JavaScript PlanosManager
  - [x] 5.1 Implementar el módulo `PlanosManager` con métodos de carga y renderizado en `proyecto_detalle_fiori.html`
    - Definir objeto `PlanosManager` con estado: `{proyectoId, currentPage, totalPages}`
    - Método `init(proyectoId)`: guardar proyectoId, bind events de la pestaña (lazy load al activar "Planos PDF")
    - Método `loadPlanos(page)`: fetch GET a `/proyectos/proyecto/${proyectoId}/planos/?page=${page}`, llamar `renderTable(data)`
    - Método `renderTable(data)`: generar filas HTML, actualizar paginación, mostrar/ocultar empty state
    - Método `renderPagination(total, page, totalPages)`: generar controles anterior/siguiente
    - En caso de error de fetch: toast SweetAlert2 con mensaje de error
    - _Requirements: 2.5, 3.1, 3.3, 7.2, 7.6_

  - [x] 5.2 Implementar la lógica de upload con dropzone en `PlanosManager`
    - Método `initDropzone()`: bind eventos dragover, dragleave, drop en el área de dropzone
    - Método `uploadPlano(file, titulo, descripcion)`: construir FormData, fetch POST multipart a `/proyectos/proyecto/${proyectoId}/planos/upload/`
    - Validación client-side: solo archivos .pdf, tamaño <= 50 MB
    - Mostrar progress indicator durante la carga
    - En éxito: toast success, llamar `loadPlanos(1)` para refrescar
    - En error: toast error con mensaje del servidor
    - Limpiar formulario y resetear dropzone tras carga exitosa
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

  - [x] 5.3 Implementar la lógica de eliminación en `PlanosManager`
    - Método `deletePlano(planoId, titulo)`: mostrar SweetAlert2 de confirmación con título del plano
    - En confirmación: fetch DELETE a `/proyectos/proyecto/${proyectoId}/planos/${planoId}/delete/`
    - En éxito: toast success, refrescar lista con `loadPlanos(currentPage)`
    - En error: toast error, mantener lista sin cambios
    - En cancelar: cerrar diálogo sin acción
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [x] 6. Checkpoint - Verificar funcionalidad de pestaña completa
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Frontend: Visor PDF standalone
  - [x] 7.1 Crear template `proyectos/templates/proyectos/visor_plano_proyecto.html`
    - Basado en el patrón de `core/templates/activos/visor_pdf_plano.html` pero simplificado (sin pines ni anotaciones)
    - Toolbar superior: título del plano, nombre del proyecto, controles de navegación
    - Controles de zoom: botones zoom in/out (rango 25%-400%), botón "Ajustar" (fit), botón "1:1"
    - Navegación de páginas: botones anterior/siguiente, indicador "Página X de Y"
    - Panel lateral de miniaturas (thumbnail strip) con scroll vertical
    - Área principal de renderizado con canvas para PDF.js
    - Indicador de progreso durante la carga del PDF
    - Pantalla de error si el archivo no está disponible con botón "Volver al proyecto"
    - Cargar PDF.js desde CDN versión 3.11.174 (misma que usa el visor de activos)
    - _Requirements: 4.1, 4.2, 4.5_

- [x] 8. Backend/Frontend: Integración final
  - [x] 8.1 Conectar el sistema de pestañas para lazy-load de datos al activar "Planos PDF"
    - Agregar listener de clic en la pestaña `data-target="planos-pdf"` que invoque `PlanosManager.init()`
    - Solo cargar datos la primera vez que se activa la pestaña (lazy loading)
    - Pasar `{{ proyecto.pk }}` como proyectoId al inicializar
    - _Requirements: 1.2_

  - [x] 8.2 Registrar el modelo en `proyectos/admin.py`
    - Agregar `PlanoProyectoAdmin` con list_display, list_filter, search_fields
    - Opcionalmente, agregar inline en ProyectoAdmin
    - _Requirements: 6.1_

- [ ] 9. Testing
  - [ ]* 9.1 Escribir property test para validación de tipo de archivo
    - **Property 1: Validación de tipo de archivo rechaza no-PDF**
    - Generar archivos con extensiones y content-types aleatorios que no sean PDF
    - Verificar que el endpoint retorna 400 sin crear registro
    - Usar `hypothesis` con `@settings(max_examples=100)`
    - **Validates: Requirements 2.3, 6.4, 6.5**

  - [ ]* 9.2 Escribir property test para validación de campos de entrada
    - **Property 2: Validación de campos de entrada**
    - Generar títulos con longitudes fuera de [1, 200] y descripciones > 500 chars
    - Verificar que el endpoint retorna 400 sin crear registro
    - Usar `hypothesis` con `@settings(max_examples=100)`
    - **Validates: Requirements 2.6**

  - [ ]* 9.3 Escribir property test para round-trip carga-listado
    - **Property 3: Round-trip de carga y listado**
    - Generar datos válidos (título, descripción, archivo PDF), subir y verificar presencia en listado
    - Verificar que todos los campos requeridos están presentes en la respuesta
    - Usar `hypothesis` con `@settings(max_examples=100)`
    - **Validates: Requirements 2.2, 3.1, 7.2**

  - [ ]* 9.4 Escribir property test para orden y paginación
    - **Property 4: Orden descendente y paginación**
    - Generar conjuntos de planos, verificar orden descendente por fecha_carga y correcta paginación
    - Verificar campos total, page, total_pages
    - Usar `hypothesis` con `@settings(max_examples=100)`
    - **Validates: Requirements 3.3, 7.6**

  - [ ]* 9.5 Escribir property test para eliminación
    - **Property 5: Eliminación remueve del listado**
    - Crear planos, eliminar uno, verificar que no aparece en listado posterior
    - Usar `hypothesis` con `@settings(max_examples=100)`
    - **Validates: Requirements 5.3**

  - [ ]* 9.6 Escribir property test para cascade delete
    - **Property 6: Eliminación en cascada al borrar proyecto**
    - Crear proyecto con N planos, eliminar proyecto, verificar que no quedan registros
    - Usar `hypothesis` con `@settings(max_examples=100)`
    - **Validates: Requirements 6.3**

  - [ ]* 9.7 Escribir property test para Content-Disposition en descarga
    - **Property 7: Content-Disposition en descarga**
    - Generar títulos aleatorios, verificar header correcto en respuesta de descarga
    - Usar `hypothesis` con `@settings(max_examples=100)`
    - **Validates: Requirements 4.3**

  - [ ]* 9.8 Escribir property test para formato JSON consistente
    - **Property 8: Formato JSON consistente**
    - Generar solicitudes válidas e inválidas, verificar que respuestas siempre tienen `status` y `message`
    - Usar `hypothesis` con `@settings(max_examples=100)`
    - **Validates: Requirements 7.5**

- [x] 10. Final checkpoint - Verificar integración completa
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- El modelo `PlanoProyecto` es nuevo y requiere migración
- La pestaña "Planos PDF" se inserta entre "Documentos vinculados" (data-target="documentos") y "Órdenes de Trabajo" (data-target="visor")
- El visor PDF se basa en `core/templates/activos/visor_pdf_plano.html` pero sin pines/anotaciones
- MinIO storage se importa con: `from core.storage import MinIOStorage; minio_storage = MinIOStorage()`
- PDF.js CDN versión 3.11.174 (consistente con el visor existente)
- SweetAlert2 ya está incluido en el template principal
- URLs existentes siguen el patrón: `proyecto/<int:pk>/...`
- Archivos de test property-based se crean en `proyectos/tests.py` o un módulo `proyectos/tests/` dedicado

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["2.1", "2.2", "2.3", "2.4", "2.5", "2.6"] },
    { "id": 3, "tasks": ["4.1", "4.2", "4.3", "7.1"] },
    { "id": 4, "tasks": ["5.1", "8.2"] },
    { "id": 5, "tasks": ["5.2", "5.3"] },
    { "id": 6, "tasks": ["8.1"] },
    { "id": 7, "tasks": ["9.1", "9.2", "9.3", "9.4", "9.5", "9.6", "9.7", "9.8"] }
  ]
}
```
