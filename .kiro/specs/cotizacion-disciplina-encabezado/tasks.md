# Implementation Plan: cotizacion-disciplina-encabezado

## Overview

Rediseño del formulario de cotizaciones para soportar múltiples disciplinas. Se migra `Cotizacion.disciplina` a nullable, se adaptan las vistas Python, se reescribe la estructura HTML del template y se reemplaza toda la lógica JavaScript de ítems por un sistema de secciones dinámicas por disciplina.

## Task Dependency Graph

```json
{
  "waves": [
    {
      "wave": 1,
      "tasks": [1, 2],
      "description": "Capa de datos y vistas — independientes entre sí"
    },
    {
      "wave": 2,
      "tasks": [3],
      "description": "Estructura HTML del template — requiere saber qué pasa el contexto (Task 2)"
    },
    {
      "wave": 3,
      "tasks": [4],
      "description": "Implementación JavaScript de secciones — requiere el HTML base (Task 3)"
    },
    {
      "wave": 4,
      "tasks": [5],
      "description": "Reconstrucción en modo edición — usa las funciones JS de Task 4"
    }
  ]
}
```

---

## Tasks

- [ ] 1. Migración de modelo — Cotizacion.disciplina nullable

  Hacer el campo `Cotizacion.disciplina` opcional en el modelo y en la base de datos.

  ### Sub-tasks

  - [ ] 1.1 Actualizar `presupuestos/models.py`: agregar `null=True, blank=True` al `ForeignKey` de `Cotizacion.disciplina`
  - [ ] 1.2 Actualizar `Cotizacion.__str__` para que no falle cuando `disciplina` es `None` (usar `self.disciplina.nombre if self.disciplina else "Sin disciplina"`)
  - [ ] 1.3 Crear la migración Django ejecutando `python manage.py makemigrations presupuestos --name cotizacion_disciplina_nullable`
  - [ ] 1.4 Verificar que la migración generada contiene `AlterField` con `null=True, blank=True` para `cotizacion.disciplina`
  - [ ] 1.5 Aplicar la migración con `python manage.py migrate presupuestos` y confirmar que no hay errores

  ### Archivos
  - `presupuestos/models.py`
  - `presupuestos/migrations/XXXX_cotizacion_disciplina_nullable.py` (generado)

  ### Criterios de aceptación
  - `Cotizacion.objects.create(numero=..., fecha=..., creado_por=...)` sin `disciplina` no lanza `IntegrityError`
  - Los registros existentes conservan su `disciplina_id` original
  - `str(cotizacion)` no lanza `AttributeError` cuando `disciplina=None`

---

- [ ] 2. Actualizar vistas Python

  Adaptar `crear_cotizacion` y `editar_cotizacion` para que trabajen con disciplina por ítem en lugar de disciplina global en encabezado.

  ### Sub-tasks

  - [ ] 2.1 En `crear_cotizacion` POST: quitar validación `if not disciplina_id` (reemplazar por `if not fecha`)
  - [ ] 2.2 En `crear_cotizacion` POST: crear `Cotizacion` con `disciplina=None` (eliminar `disciplina_id=disciplina_id`)
  - [ ] 2.3 En `crear_cotizacion` POST: en el loop de ítems usar `disciplina_id=item.get('disciplina_id') or None`
  - [ ] 2.4 En `editar_cotizacion` POST `guardar_cabecera`: eliminar la línea `cotizacion.disciplina_id = request.POST.get('disciplina')`
  - [ ] 2.5 En `editar_cotizacion` POST `guardar_items`: en el loop de ítems usar `disciplina_id=item.get('disciplina_id') or None`
  - [ ] 2.6 En `editar_cotizacion` GET: construir `items_por_disciplina` usando `defaultdict`, agrupando ítems por `item.disciplina_id`
  - [ ] 2.7 En `editar_cotizacion` GET: serializar el dict a JSON con `json.dumps()` y pasarlo al contexto como `items_por_disciplina_json`
  - [ ] 2.8 Confirmar que el contexto del GET de `editar_cotizacion` ya no incluye la variable `items` plana (se reemplaza por `items_por_disciplina_json`)

  ### Archivos
  - `presupuestos/views.py`

  ### Criterios de aceptación
  - POST a `/cotizaciones/crear/` con JSON de ítems que incluyen `disciplina_id` crea los `ItemCotizacion` con la disciplina correcta
  - POST `guardar_cabecera` no modifica `cotizacion.disciplina_id`
  - GET de edición retorna `items_por_disciplina_json` con formato `[{disciplina_id, disciplina_nombre, items: [...]}]`
  - Ítems con `disciplina=None` se agrupan con `disciplina_id: null` y `disciplina_nombre: "Sin disciplina"`

---

- [ ] 3. Reescribir template — encabezado y estructura base

  Modificar `form_cotizacion.html` para eliminar el selector de disciplina del encabezado y agregar la zona de secciones dinámicas.

  ### Sub-tasks

  - [ ] 3.1 En el bloque `{% if es_nuevo %}`: eliminar el `<div class="field-group">` que contiene `<select name="disciplina" id="disciplina-encabezado" required>`
  - [ ] 3.2 En el bloque `{% else %}` (modo edición): eliminar el `<div class="field-group">` que contiene `<select name="disciplina" id="disciplina-encabezado" required>`
  - [ ] 3.3 Reemplazar la `card` de ítems (con `#items-table` y `#items-body`) por `<div id="secciones-container"></div>`
  - [ ] 3.4 Agregar la card `#agregar-seccion-card` con `<select id="select-nueva-disciplina">` poblado desde `{% for d in disciplinas %}` y el botón `agregarSeccionDesdeSelector()`
  - [ ] 3.5 Agregar el bloque de Total General (`<span id="total-general">`) debajo de todas las secciones
  - [ ] 3.6 En modo creación: mover el `<input type="hidden" name="items" id="items-json">` dentro del `#crear-form` (si no está ya)
  - [ ] 3.7 En modo edición: mantener `<input type="hidden" name="items" id="items-json">` dentro de `#items-form`
  - [ ] 3.8 Agregar bloque `{% if not es_nuevo %}<script>var ITEMS_POR_DISCIPLINA = {{ items_por_disciplina_json|safe }};</script>{% endif %}` antes del script principal

  ### Archivos
  - `presupuestos/templates/presupuestos/form_cotizacion.html`

  ### Criterios de aceptación
  - El encabezado no muestra ningún selector de disciplina en modo creación ni edición
  - `<div id="secciones-container">` existe en el DOM
  - `<select id="select-nueva-disciplina">` contiene las disciplinas disponibles
  - `<span id="total-general">` existe en el DOM
  - La variable `ITEMS_POR_DISCIPLINA` está disponible en modo edición

---

- [ ] 4. Implementar JavaScript — secciones dinámicas

  Escribir las funciones JS que gestionan el ciclo de vida de las secciones y sus ítems.

  ### Sub-tasks

  - [ ] 4.1 Eliminar declaración `var DISCIPLINA_ID = ...`
  - [ ] 4.2 Agregar declaración `var API_ITEMS_URL = '{% url "presupuestos:api_items_por_disciplina" 0 %}'`
  - [ ] 4.3 Implementar función auxiliar `buildItemRowHTML(idx, desc, um, cant, pu, dto, predefinidoId)` que retorna el HTML string de una fila `<tr>`
  - [ ] 4.4 Implementar `buildSeccionHTML(disciplinaId, disciplinaNombre)` que retorna el HTML string de la estructura interna de la sección (card + tabla + toolbar)
  - [ ] 4.5 Implementar `agregarSeccion(disciplinaId, disciplinaNombre)`: verifica duplicados, crea `<div class="seccion-disciplina">`, lo agrega a `#secciones-container`, retorna el div o `null` si ya existe
  - [ ] 4.6 Implementar `agregarSeccionDesdeSelector()`: lee `#select-nueva-disciplina`, llama `agregarSeccion()`, resetea el select
  - [ ] 4.7 Implementar `eliminarSeccion(btn)`: `confirm()`, `seccionDiv.remove()`, llama `recalcularTotalGeneral()`
  - [ ] 4.8 Implementar `agregarItemEnSeccion(btn)`: obtiene el `.seccion-items-body` padre, agrega fila vacía con `buildItemRowHTML`, llama `actualizarIndicesSeccion` y `recalcularSeccion`
  - [ ] 4.9 Implementar `eliminarItemDeSeccion(btn)`: elimina `<tr>`, llama `actualizarIndicesSeccion` y `recalcularSeccion`
  - [ ] 4.10 Implementar `recalcularItemEnSeccion(el)`: calcula total de la fila, actualiza `.item-total`, llama `recalcularSeccion`
  - [ ] 4.11 Implementar `actualizarIndicesSeccion(tbody)`: renumera las filas del tbody dado
  - [ ] 4.12 Implementar `recalcularSeccion(seccionDiv)`: suma `.item-total` del seccionDiv, actualiza `.seccion-subtotal` y `.seccion-total`, llama `recalcularTotalGeneral()`
  - [ ] 4.13 Implementar `recalcularTotalGeneral()`: suma todos los `.seccion-subtotal` del DOM, actualiza `#total-general`
  - [ ] 4.14 Implementar `cargarPredefinidosEnSeccion(btn)`: obtiene `disciplinaId` del `seccionDiv`, hace `fetch` a `API_ITEMS_URL`, agrega ítems al tbody sin borrar los existentes, muestra alerta si lista vacía
  - [ ] 4.15 Implementar `recolectarTodosLosItems()`: recorre `.seccion-disciplina`, por cada una recorre `.seccion-items-body tr` y genera `{disciplina_id, item_predefinido_id, descripcion, unidad_medida, cantidad, precio_unitario, descuento_porcentaje}`
  - [ ] 4.16 Actualizar `antesDeCrear(e)`: usar `recolectarTodosLosItems()` en lugar de `recolectarItems()`
  - [ ] 4.17 Actualizar `guardarItems()`: usar `recolectarTodosLosItems()` en lugar de `recolectarItems()`
  - [ ] 4.18 Eliminar funciones obsoletas: `cargarPredefinidos()`, `agregarVacio()`, `recolectarItems()`, `recalcularItem()`, `recalcularTotal()`, `actualizarIndices()`
  - [ ] 4.19 Eliminar el listener `onchange` de `#disciplina-encabezado` del `DOMContentLoaded`

  ### Archivos
  - `presupuestos/templates/presupuestos/form_cotizacion.html`

  ### Criterios de aceptación
  - Click en "Agregar sección" con disciplina nueva → nueva card aparece en `#secciones-container`
  - Click en "Agregar sección" con disciplina duplicada → alerta, no crea sección duplicada
  - Click en "+ Agregar ítem" → fila vacía aparece en el tbody de esa sección
  - Editar cantidad/precio/descuento → subtotal de sección y total general se actualizan en tiempo real
  - Click en "⬇ Cargar predefinidos" → ítems se agregan al final del tbody (no borra los existentes)
  - Click en "🗑 Eliminar sección" → confirm(), sección desaparece, total general se recalcula
  - `recolectarTodosLosItems()` retorna array con `disciplina_id` correcto por cada ítem

---

- [ ] 5. Reconstrucción de secciones en modo edición

  Al abrir el formulario de edición, reconstruir las secciones desde `ITEMS_POR_DISCIPLINA` usando las funciones del Task 4.

  ### Sub-tasks

  - [ ] 5.1 En el bloque `DOMContentLoaded`: agregar verificación `if (typeof ITEMS_POR_DISCIPLINA !== 'undefined' && ITEMS_POR_DISCIPLINA.length)`
  - [ ] 5.2 Por cada elemento de `ITEMS_POR_DISCIPLINA`: llamar `agregarSeccion(seccion.disciplina_id, seccion.disciplina_nombre)`
  - [ ] 5.3 Por cada ítem de `seccion.items`: obtener el `tbody` del div retornado, crear `<tr>` con `buildItemRowHTML()`, appendear al tbody
  - [ ] 5.4 Llamar `actualizarIndicesSeccion(tbody)` y `recalcularSeccion(div)` al terminar de cargar cada sección
  - [ ] 5.5 Verificar que ítems con `disciplina_id = null` se cargan bajo la sección "Sin disciplina"
  - [ ] 5.6 Verificar que al abrir una cotización existente con múltiples disciplinas, se crean N secciones con los ítems correspondientes
  - [ ] 5.7 Verificar que después de la reconstrucción el Total General refleja la suma correcta de todos los ítems

  ### Archivos
  - `presupuestos/templates/presupuestos/form_cotizacion.html`

  ### Criterios de aceptación
  - Al editar una cotización con ítems de 2 disciplinas distintas → 2 secciones visibles con sus ítems precargados
  - Subtotal de cada sección muestra el valor correcto al cargar
  - Total General muestra la suma correcta al cargar
  - La edición de ítems después de la reconstrucción funciona igual que en modo creación
  - Guardar después de edición envía el JSON correcto con `disciplina_id` en cada ítem


---

## Notes

- Ejecutar `python manage.py makemigrations presupuestos` después de editar `models.py` (Task 1.3); el nombre sugerido es `cotizacion_disciplina_nullable`.
- Las tareas 1 y 2 son independientes y pueden ejecutarse en paralelo.
- La función `buildItemRowHTML` es compartida por Tasks 4 y 5 — implementarla primero dentro del Task 4 antes de usarla en el Task 5.
- Cotizaciones existentes con `disciplina != None` no necesitan migración de datos; sus ítems que tengan `ItemCotizacion.disciplina = None` aparecerán en una sección "Sin disciplina" al editar.
- La vista `ver_cotizacion` y `cotizacion_pdf` no requieren cambios en este plan; pueden adaptarse en un feature separado para agrupar ítems por disciplina en la vista de solo lectura.
