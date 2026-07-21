## Objective
- Generar un libro PDF descargable de cada curso, que incluya todas las secciones, páginas, acordeones y carruseles; y que cada página pueda tener sus propios acordeones, carruseles e imágenes interactivas en el editor

## Important Details
- CSS leak fix: `sanitizarPreview()` ya no remueve `<style>` — ahora se usa **Shadow DOM** (`pc()` helper) para aislar los estilos del usuario dentro del preview sin afectar la página padre
- Los modelos `Acordeon`, `Carrusel`, `ImagenInteractiva` ya tenían FK a `Pagina` (nullable) — solo faltaba la UI del editor
- Las funciones `agregarAcordeon()`, `crearCarrusel()`, `crearImagenInteractiva()` ya aceptaban `pagina_id` — el backend no requirió cambios
- Se usa `xhtml2pdf` (mismo patrón que `presupuestos`) para generar PDF; compatible con tablas, imágenes, `@page`, `pdf:toc`
- El PDF debe incluir portada, índice, secciones, páginas, acordeones y carruseles
- El PDF es accesible para staff y estudiantes con asignación al curso
- Bug (fixed): en el editor de cursos, las secciones 2+ quedaban anidadas dentro de la sección 1 porque `seccion-body` y `seccion-item` nunca se cerraban antes de `{% endfor %}`

## Work State
### Completed
- **CSS isolation vía Shadow DOM**: reemplazó `sanitizarPreview()` (que eliminaba `<style>`) por `pc(el)` helper que adjunta un shadow root a cada `.html-preview`; todos los renders (`actualizarPreview`, `cambiarModoPreview`, `cambiarModoPagina`, `actualizarPreviewPag`) y herramientas (`tbCmd`, `tbInsertImage`, `tbInsertVideo`) ahora operan sobre el shadow root; `ph(el)` helper cruza la frontera shadow para eventos; observer `base64Observer` observa el shadow root; listeners de `input`/`paste`/`click` actualizados con `ph()`/`pc()`; resizer de imágenes usa `getRootNode().host`
- **Vista `libro_pdf()`**: `courses/views.py:1191` — genera PDF con xhtml2pdf, incluye secciones, páginas, acordeones, carruseles; accesible via `@login_required` con verificación de asignación
- **Template `libro_pdf.html`**: portada con título/fecha, índice (`<pdf:toc>`), cada sección con su contenido + páginas + acordeones + carruseles, estilos compatibles con xhtml2pdf (tablas, imágenes, código, blockquotes)
- **URL**: `courses/urls.py:31` — `admin/<int:pk>/libro-pdf/` → `courses:libro_pdf`
- **Botón PDF en admin**: `admin_lista.html` — botón `📖 PDF` para cursos padres e hijos
- **Botón PDF en estudiante**: `detalle.html:504` — botón `📖 PDF` en el header del visor
- **Page-level components en editor**: `_paginas_list.html` — cada página renderiza `imagenes_interactivas`, `acordeones`, `carruseles` con edición inline y botones para agregar nuevos; CSS `.pag-comp-*` agregado en `editor.html`
- **Prefetch en `gestionar_pagina`**: `views.py:345,356` — `prefetch_related('imagenes_interactivas__hotspots', 'acordeones', 'carruseles__tarjetas')` evita N+1
- **PDF actualizado**: `libro_pdf.html` — incluye acordeones y carruseles de cada página
- **Bug fix: secciones anidadas**: `editor.html` — se agregaron `</div>` faltantes para cerrar `seccion-body` (line 488) y `seccion-item` (line 489) antes de `{% endwith %}`/`{% endfor %}`, evitando que las secciones 2+ quedaran dentro de la sección 1

### Active
- (none)

### Blocked
- (none)

## Next Move
1. Probar `/courses/admin/<id>/libro-pdf/` y verificar que el PDF descarga correctamente con todo el contenido
2. Probar el editor con múltiples secciones para confirmar que ya no se anidan dentro de la sección 1

## Relevant Files
- `courses/templates/courses/editor.html:984-1009`: `sanitizarPreview()` (sin filtro de `<style>`), helpers `pc()`/`ph()`, Shadow DOM
- `courses/templates/courses/editor.html:950-980,990-1010,1020-1060,1075-1090`: funciones actualizadas para usar `pc(preview)` / `ph()`
- `courses/templates/courses/editor.html:847-870`: `base64Observer` observa `pc(preview)`
- `courses/templates/courses/editor.html:1705-1725`: eventos click/mousedown con `ph(img)`
- `courses/templates/courses/editor.html:1775-1810`: resize/remove image con `getRootNode().host`
- `courses/templates/courses/editor.html:486-491`: Fix — closes `seccion-body` and `seccion-item` before `{% endwith %}`
- `courses/templates/courses/editor.html`: nuevas CSS `.pag-comp-*` para componentes de página
- `courses/templates/courses/_paginas_list.html`: renderiza `imagenes_interactivas`, `acordeones`, `carruseles` por página + botones de acción
- `courses/views.py:1191-1231`: `libro_pdf()` view
- `courses/views.py:345,356`: `prefetch_related` en `gestionar_pagina`
- `courses/urls.py:31`: ruta `admin/<pk>/libro-pdf/`
- `courses/templates/courses/libro_pdf.html`: template del libro PDF con portada, TOC, secciones, páginas, acordeones, carruseles
- `courses/templates/courses/admin_lista.html`: botón `📖 PDF` en admin
- `courses/templates/courses/detalle.html:504`: botón `📖 PDF` en header estudiante
