# Diseño Técnico — cotizacion-disciplina-encabezado

## Overview

Rediseño del formulario de cotizaciones para soportar múltiples disciplinas dentro de una misma cotización. El campo `Cotizacion.disciplina` pasa a ser nullable y el agrupador real de los ítems es `ItemCotizacion.disciplina`. La UI pasa de una tabla única a un conjunto de **secciones por disciplina**, cada una con su propia tabla, botones de acción y subtotal.

---

## 1. Cambios de Modelo

### 1.1 `Cotizacion.disciplina` — nullable

**Archivo:** `presupuestos/models.py`

Cambio en la definición del campo:

```python
# ANTES
disciplina = models.ForeignKey(
    'documentos.Disciplina', on_delete=models.PROTECT,
    related_name='cotizaciones', verbose_name="Disciplina"
)

# DESPUÉS
disciplina = models.ForeignKey(
    'documentos.Disciplina', on_delete=models.PROTECT,
    null=True, blank=True,
    related_name='cotizaciones', verbose_name="Disciplina"
)
```

También actualizar el método `__str__` para que no falle cuando `disciplina` es `None`:

```python
def __str__(self):
    disc = self.disciplina.nombre if self.disciplina else "Sin disciplina"
    return f"{self.numero} - {disc}"
```

### 1.2 Migración Django

**Archivo:** `presupuestos/migrations/XXXX_cotizacion_disciplina_nullable.py`

```python
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ('presupuestos', 'XXXX_previous_migration'),
        ('documentos', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cotizacion',
            name='disciplina',
            field=models.ForeignKey(
                'documentos.Disciplina',
                on_delete=django.db.models.deletion.PROTECT,
                null=True,
                blank=True,
                related_name='cotizaciones',
                verbose_name="Disciplina",
            ),
        ),
    ]
```

> **Nota:** No se modifica `ItemCotizacion.disciplina` — ya es `null=True, blank=True` y actúa como agrupador de sección.

---

## Architecture

El feature opera enteramente dentro del módulo `presupuestos` de Django, sin nuevas dependencias externas. La arquitectura sigue el patrón MVT existente:

- **Model layer:** `Cotizacion` (campo nullable) + `ItemCotizacion` (agrupador por disciplina, ya nullable).
- **View layer:** `crear_cotizacion` y `editar_cotizacion` en `views.py` reciben y emiten JSON de ítems con `disciplina_id` por ítem.
- **Template layer:** `form_cotizacion.html` con HTML/JS vanilla genera y gestiona las secciones en el cliente; serializa el estado a JSON antes del POST.
- **API:** Endpoint existente `api_items_por_disciplina` consumido desde el cliente via `fetch()` — sin cambios.

El estado de las secciones y sus ítems reside íntegramente en el DOM durante la sesión de edición. No hay estado en memoria adicional ni localStorage; la persistencia se logra al serializar el DOM a JSON en el submit del formulario.

---

## Components and Interfaces

### Componente: `Cotizacion` (modelo)

| Campo | Antes | Después |
|---|---|---|
| `disciplina` | `ForeignKey(NOT NULL)` | `ForeignKey(null=True, blank=True)` |

### Componente: `crear_cotizacion` (vista)

- **Entrada POST:** `proyecto`, `fecha`, `version`, `valida_hasta`, `notas`, `items` (JSON)
- **JSON de ítems esperado:** `[{disciplina_id, descripcion, unidad_medida, cantidad, precio_unitario, descuento_porcentaje, item_predefinido_id}]`
- **Salida:** Crea `Cotizacion(disciplina=None)` + N `ItemCotizacion` con `disciplina_id` por ítem

### Componente: `editar_cotizacion` (vista)

- **GET — contexto extra:** `items_por_disciplina_json` (string JSON) con estructura `[{disciplina_id, disciplina_nombre, items:[...]}]`
- **POST `guardar_cabecera`:** actualiza proyecto, fecha, versión, notas — NO toca `disciplina_id`
- **POST `guardar_items`:** borra todos los `ItemCotizacion` y los recrea con `disciplina_id` del JSON

### Componente: Secciones JS (`form_cotizacion.html`)

Interfaz de funciones públicas:

| Función | Firma | Descripción |
|---|---|---|
| `agregarSeccion` | `(disciplinaId, disciplinaNombre) → div\|null` | Crea sección o alerta si duplicada |
| `agregarSeccionDesdeSelector` | `() → void` | Lee el select y llama `agregarSeccion` |
| `eliminarSeccion` | `(btn) → void` | Confirm + elimina sección del DOM |
| `agregarItemEnSeccion` | `(btn) → void` | Agrega fila vacía al tbody de la sección |
| `eliminarItemDeSeccion` | `(btn) → void` | Elimina fila del tbody |
| `cargarPredefinidosEnSeccion` | `(btn) → void` | Fetch API + agrega ítems al tbody |
| `recalcularItemEnSeccion` | `(el) → void` | Recalcula fila + sección + total general |
| `recalcularSeccion` | `(seccionDiv) → void` | Suma ítems de la sección |
| `recalcularTotalGeneral` | `() → void` | Suma subtotales de todas las secciones |
| `recolectarTodosLosItems` | `() → Array` | Serializa DOM a array de ítems con `disciplina_id` |
| `buildItemRowHTML` | `(idx, desc, um, cant, pu, dto, predId) → string` | HTML de fila de ítem |
| `buildSeccionHTML` | `(disciplinaId, nombre) → string` | HTML de sección (card+tabla+toolbar) |
| `actualizarIndicesSeccion` | `(tbody) → void` | Renumera filas de un tbody |

---

## Data Models

### `Cotizacion` (modificado)

```python
class Cotizacion(models.Model):
    numero       = models.CharField(max_length=20, unique=True)
    proyecto     = models.ForeignKey('proyectos.Proyecto', null=True, blank=True, ...)
    disciplina   = models.ForeignKey('documentos.Disciplina', null=True, blank=True, ...)  # CAMBIA
    fecha        = models.DateField()
    version      = models.PositiveIntegerField(default=1)
    valida_hasta = models.DateField(null=True, blank=True)
    estado       = models.CharField(choices=ESTADOS, default='BORRADOR')
    creado_por   = models.ForeignKey(User, null=True, ...)
    notas        = models.TextField(blank=True)
```

### `ItemCotizacion` (sin cambios)

```python
class ItemCotizacion(models.Model):
    cotizacion         = models.ForeignKey(Cotizacion, related_name='items', ...)
    item_predefinido   = models.ForeignKey(ItemPredefinido, null=True, blank=True, ...)
    disciplina         = models.ForeignKey('documentos.Disciplina', null=True, blank=True, ...)  # agrupador de sección
    descripcion        = models.TextField()
    unidad_medida      = models.CharField(max_length=50)
    cantidad           = models.DecimalField(max_digits=12, decimal_places=2)
    precio_unitario    = models.DecimalField(max_digits=15, decimal_places=2)
    descuento_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    orden              = models.PositiveIntegerField(default=0)
```

### Estructura JSON de `items_por_disciplina_json` (contexto GET edición)

```json
[
  {
    "disciplina_id": 3,
    "disciplina_nombre": "Electricidad",
    "items": [
      {
        "id": 101,
        "disciplina_id": 3,
        "disciplina_nombre": "Electricidad",
        "item_predefinido_id": 42,
        "descripcion": "Cable 2.5mm²",
        "unidad_medida": "ml",
        "cantidad": 100.0,
        "precio_unitario": 1250.0,
        "descuento_porcentaje": 5.0
      }
    ]
  },
  {
    "disciplina_id": null,
    "disciplina_nombre": "Sin disciplina",
    "items": [...]
  }
]
```

---
 (`presupuestos/views.py`)

### 2.1 `crear_cotizacion` — POST

**Cambios:**
- Eliminar validación `if not disciplina_id`.
- Crear `Cotizacion` con `disciplina=None` (no se lee `disciplina_id` del POST del encabezado).
- Leer `disciplina_id` de cada ítem en el JSON y pasarlo a `ItemCotizacion.objects.create(...)`.

```python
# ANTES
if not disciplina_id or not fecha:
    messages.error(request, 'Disciplina y fecha son requeridos.')
    return redirect('presupuestos:crear_cotizacion')

cotizacion = Cotizacion.objects.create(
    numero=numero,
    proyecto_id=proyecto_id or None,
    disciplina_id=disciplina_id,
    ...
)

for idx, item in enumerate(items):
    ItemCotizacion.objects.create(
        ...
        disciplina_id=cotizacion.disciplina_id,
        ...
    )

# DESPUÉS
if not fecha:
    messages.error(request, 'La fecha es requerida.')
    return redirect('presupuestos:crear_cotizacion')

cotizacion = Cotizacion.objects.create(
    numero=numero,
    proyecto_id=proyecto_id or None,
    disciplina=None,
    ...
)

for idx, item in enumerate(items):
    ItemCotizacion.objects.create(
        ...
        disciplina_id=item.get('disciplina_id') or None,
        ...
    )
```

### 2.2 `editar_cotizacion` — POST `guardar_cabecera`

Eliminar la línea que asigna disciplina desde el POST:

```python
# ELIMINAR esta línea:
cotizacion.disciplina_id = request.POST.get('disciplina')
```

### 2.3 `editar_cotizacion` — POST `guardar_items`

Usar `disciplina_id` del ítem JSON en lugar del de la cotización:

```python
# ANTES
ItemCotizacion.objects.create(
    ...
    disciplina_id=cotizacion.disciplina_id,
    ...
)

# DESPUÉS
ItemCotizacion.objects.create(
    ...
    disciplina_id=item.get('disciplina_id') or None,
    ...
)
```

### 2.4 `editar_cotizacion` — GET (contexto para modo edición)

Agregar `items_por_disciplina` al contexto: dict donde la clave es la disciplina y el valor es la lista de ítems serializada.

```python
# Construir dict agrupado por disciplina
from collections import defaultdict
import json as json_mod

items = cotizacion.items.select_related('disciplina').order_by('orden')
grupos = defaultdict(list)
for item in items:
    key = item.disciplina_id  # puede ser None
    grupos[key].append({
        'id': item.id,
        'disciplina_id': item.disciplina_id,
        'disciplina_nombre': item.disciplina.nombre if item.disciplina else 'Sin disciplina',
        'item_predefinido_id': item.item_predefinido_id,
        'descripcion': item.descripcion,
        'unidad_medida': item.unidad_medida,
        'cantidad': float(item.cantidad),
        'precio_unitario': float(item.precio_unitario),
        'descuento_porcentaje': float(item.descuento_porcentaje),
    })

# Construir lista de secciones ordenadas
items_por_disciplina = []
for disc_id, items_list in grupos.items():
    nombre = items_list[0]['disciplina_nombre']
    items_por_disciplina.append({
        'disciplina_id': disc_id,
        'disciplina_nombre': nombre,
        'items': items_list,
    })

return render(request, 'presupuestos/form_cotizacion.html', {
    'cotizacion': cotizacion,
    'disciplinas': disciplinas,
    'proyectos': proyectos,
    'items_por_disciplina_json': json_mod.dumps(items_por_disciplina),
    'es_nuevo': False,
    'ESTADOS': Cotizacion.ESTADOS,
})
```

---

## 3. Cambios de Template (`form_cotizacion.html`)

### 3.1 Encabezado — eliminar selector de disciplina

En ambos bloques (`es_nuevo` y edición), eliminar el `field-group` que contiene:
```html
<!-- ELIMINAR en modo creación -->
<div class="field-group">
    <label>Disciplina *</label>
    <select name="disciplina" id="disciplina-encabezado" required>...</select>
</div>

<!-- ELIMINAR en modo edición -->
<div class="field-group">
    <label>Disciplina *</label>
    <select name="disciplina" id="disciplina-encabezado" required>...</select>
</div>
```

El encabezado queda con: Proyecto, Fecha, Versión, Válida hasta, Notas.

### 3.2 Zona de secciones dinámicas

Reemplazar la `card` de items (con su `#items-table` y `#items-body` únicos) por:

```html
<!-- Contenedor de secciones por disciplina -->
<div id="secciones-container">
    <!-- Las secciones se insertan aquí dinámicamente via JS -->
</div>

<!-- Card para agregar nueva sección -->
<div class="card" id="agregar-seccion-card">
    <div class="card-body" style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
        <select id="select-nueva-disciplina" style="padding:7px 10px;border:1px solid var(--sap-border-color);font-family:var(--sap-font-family);font-size:0.88rem;min-width:220px;">
            <option value="">— Seleccione disciplina para agregar —</option>
            {% for d in disciplinas %}
            <option value="{{ d.id }}" data-nombre="{{ d.nombre }}">{{ d.nombre }}</option>
            {% endfor %}
        </select>
        <button type="button" class="btn btn-sm btn-primary" onclick="agregarSeccionDesdeSelector()">+ Agregar sección de disciplina</button>
    </div>
</div>

<!-- Total general -->
<div class="card">
    <div class="card-body" style="display:flex;align-items:center;justify-content:flex-end;gap:16px;">
        <span style="font-weight:700;font-size:0.95rem;">Total General:</span>
        <span id="total-general" style="font-weight:700;font-size:1.1rem;color:var(--sap-brand-color);">$ 0.00</span>
    </div>
</div>
```

### 3.3 HTML de una sección (generado via JS, estructura de referencia)

```html
<div class="seccion-disciplina" data-disciplina-id="123" data-disciplina-nombre="Electricidad">
    <div class="card">
        <div class="card-header">
            <span class="seccion-titulo">Electricidad</span>
            <span style="flex:1;"></span>
            <span class="seccion-subtotal" style="font-size:0.9rem;font-weight:700;margin-right:16px;">$ 0.00</span>
            <button type="button" onclick="eliminarSeccion(this)" class="btn btn-sm btn-danger">🗑 Eliminar sección</button>
        </div>
        <div class="card-body" style="padding:0;">
            <table style="width:100%;border-collapse:collapse;">
                <thead>
                    <tr>
                        <th style="width:30px;">#</th>
                        <th style="width:36px;"></th>
                        <th>Descripción</th>
                        <th>U.M.</th>
                        <th>Cantidad</th>
                        <th>Precio Unit.</th>
                        <th>Dto %</th>
                        <th style="text-align:right;">Total</th>
                        <th></th>
                    </tr>
                </thead>
                <tbody class="seccion-items-body"></tbody>
                <tfoot>
                    <tr class="total-row">
                        <td colspan="7" style="text-align:right;padding:8px 16px;font-weight:700;">Subtotal</td>
                        <td class="seccion-total" style="font-weight:700;text-align:right;padding:8px 16px;">$ 0.00</td>
                        <td></td>
                    </tr>
                </tfoot>
            </table>
        </div>
        <div class="items-toolbar">
            <button type="button" class="btn btn-sm" onclick="agregarItemEnSeccion(this)">+ Agregar ítem</button>
            <button type="button" class="btn btn-sm" onclick="cargarPredefinidosEnSeccion(this)">⬇ Cargar predefinidos</button>
        </div>
    </div>
</div>
```

### 3.4 Hidden inputs y formularios

- El hidden `#items-json` se mueve al `<form>` de creación y al `#items-form` de edición; ya existe, no cambia su nombre.
- En modo creación: `<input type="hidden" name="items" id="items-json" value="[]">` dentro de `#crear-form`.
- En modo edición: `<input type="hidden" name="items" id="items-json">` dentro de `#items-form`.

### 3.5 Variable de contexto para modo edición

```html
{% if not es_nuevo %}
<script>
    var ITEMS_POR_DISCIPLINA = {{ items_por_disciplina_json|safe }};
</script>
{% endif %}
```

---

## 4. JavaScript — Funciones nuevas y modificadas

### 4.1 Variables globales

```javascript
// URL base para la API de ítems predefinidos (inyectada desde Django)
var API_ITEMS_URL = '{% url "presupuestos:api_items_por_disciplina" 0 %}';
var COTIZACION_ID = {% if not es_nuevo %}{{ cotizacion.id }}{% else %}null{% endif %};
// NOTA: DISCIPLINA_ID se elimina; ya no hay disciplina global
```

### 4.2 `agregarSeccion(disciplinaId, disciplinaNombre)`

Crea el HTML de la sección y lo agrega a `#secciones-container`. No crea ítems.

```javascript
function agregarSeccion(disciplinaId, disciplinaNombre) {
    // Verificar que no exista ya una sección con ese disciplinaId
    var existing = document.querySelector(
        '.seccion-disciplina[data-disciplina-id="' + disciplinaId + '"]'
    );
    if (existing) {
        alert('La disciplina "' + disciplinaNombre + '" ya tiene una sección en esta cotización.');
        return null;
    }
    var container = document.getElementById('secciones-container');
    var div = document.createElement('div');
    div.className = 'seccion-disciplina';
    div.dataset.disciplinaId = disciplinaId;
    div.dataset.disciplinaNombre = disciplinaNombre;
    div.innerHTML = buildSeccionHTML(disciplinaId, disciplinaNombre);
    container.appendChild(div);
    return div;
}

function buildSeccionHTML(disciplinaId, disciplinaNombre) {
    return `
    <div class="card">
      <div class="card-header">
        <span class="seccion-titulo">${disciplinaNombre}</span>
        <span style="flex:1;"></span>
        <span class="seccion-subtotal" style="font-size:0.9rem;font-weight:700;margin-right:16px;">$ 0.00</span>
        <button type="button" onclick="eliminarSeccion(this)" class="btn btn-sm btn-danger">🗑 Eliminar sección</button>
      </div>
      <div class="card-body" style="padding:0;">
        <table style="width:100%;border-collapse:collapse;">
          <thead>
            <tr>
              <th style="width:30px;">#</th><th style="width:36px;"></th>
              <th>Descripción</th><th>U.M.</th><th>Cantidad</th>
              <th>Precio Unit.</th><th>Dto %</th>
              <th style="text-align:right;">Total</th><th></th>
            </tr>
          </thead>
          <tbody class="seccion-items-body"></tbody>
          <tfoot>
            <tr class="total-row">
              <td colspan="7" style="text-align:right;padding:8px 16px;font-weight:700;">Subtotal</td>
              <td class="seccion-total" style="font-weight:700;text-align:right;padding:8px 16px;">$ 0.00</td>
              <td></td>
            </tr>
          </tfoot>
        </table>
      </div>
      <div class="items-toolbar">
        <button type="button" class="btn btn-sm" onclick="agregarItemEnSeccion(this)">+ Agregar ítem</button>
        <button type="button" class="btn btn-sm" onclick="cargarPredefinidosEnSeccion(this)">⬇ Cargar predefinidos</button>
      </div>
    </div>`;
}
```

### 4.3 `agregarSeccionDesdeSelector()`

Lee el `<select id="select-nueva-disciplina">` y llama a `agregarSeccion()`.

```javascript
function agregarSeccionDesdeSelector() {
    var sel = document.getElementById('select-nueva-disciplina');
    var disciplinaId = sel.value;
    var disciplinaNombre = sel.options[sel.selectedIndex].dataset.nombre;
    if (!disciplinaId) {
        alert('Seleccione una disciplina antes de agregar la sección.');
        return;
    }
    var result = agregarSeccion(disciplinaId, disciplinaNombre);
    if (result) {
        sel.value = '';  // reset selector
    }
}
```

### 4.4 `eliminarSeccion(btn)`

```javascript
function eliminarSeccion(btn) {
    var seccionDiv = btn.closest('.seccion-disciplina');
    var nombre = seccionDiv.dataset.disciplinaNombre;
    if (!confirm('¿Eliminar la sección "' + nombre + '" y todos sus ítems?')) return;
    seccionDiv.remove();
    recalcularTotalGeneral();
}
```

### 4.5 `agregarItemEnSeccion(btn)`

```javascript
function agregarItemEnSeccion(btn) {
    var seccionDiv = btn.closest('.seccion-disciplina');
    var tbody = seccionDiv.querySelector('.seccion-items-body');
    var idx = tbody.children.length + 1;
    var tr = document.createElement('tr');
    tr.innerHTML = buildItemRowHTML(idx, '', 'unidad', 1, 0, 0, '');
    tbody.appendChild(tr);
    actualizarIndicesSeccion(tbody);
    recalcularSeccion(seccionDiv);
}
```

### 4.6 `buildItemRowHTML(idx, desc, um, cant, pu, dto, predefinidoId)`

Función auxiliar que genera el HTML de una fila de ítem con los valores dados. Incluye todos los `oninput="recalcularItemEnSeccion(this)"` en los campos numéricos.

```javascript
function buildItemRowHTML(idx, desc, um, cant, pu, dto, predefinidoId) {
    var S = 'border:1px solid var(--sap-border-color);padding:4px 6px;font-family:var(--sap-font-family);font-size:0.85rem;';
    var total = cant * pu * (1 - dto / 100);
    return [
        '<td class="item-idx">' + idx + '</td>',
        '<td><button type="button" onclick="eliminarItemDeSeccion(this)" style="background:none;' + S + 'cursor:pointer;color:#dc2626;font-size:0.75rem;">✕</button></td>',
        '<td><input type="text" class="item-desc" value="' + String(desc).replace(/"/g, '&quot;') + '" style="width:100%;' + S + '"></td>',
        '<td><input type="text" class="item-um" value="' + um + '" style="width:60px;' + S + '"></td>',
        '<td><input type="number" class="item-cant" step="0.01" min="0" value="' + cant + '" style="width:70px;' + S + '" oninput="recalcularItemEnSeccion(this)"></td>',
        '<td><input type="number" class="item-pu" step="0.01" min="0" value="' + pu + '" style="width:90px;' + S + '" oninput="recalcularItemEnSeccion(this)"></td>',
        '<td><input type="number" class="item-dto" step="0.01" min="0" max="100" value="' + dto + '" style="width:60px;' + S + '" oninput="recalcularItemEnSeccion(this)"></td>',
        '<td class="item-total" style="font-weight:700;text-align:right;">$ ' + total.toFixed(2) + '</td>',
        '<td><input type="hidden" class="item-predefinido-id" value="' + (predefinidoId || '') + '"></td>',
    ].join('');
}
```

### 4.7 `eliminarItemDeSeccion(btn)`

```javascript
function eliminarItemDeSeccion(btn) {
    var tr = btn.closest('tr');
    var tbody = tr.closest('tbody');
    var seccionDiv = tbody.closest('.seccion-disciplina');
    tr.remove();
    actualizarIndicesSeccion(tbody);
    recalcularSeccion(seccionDiv);
}
```

### 4.8 `recalcularItemEnSeccion(el)`

```javascript
function recalcularItemEnSeccion(el) {
    var tr = el.closest('tr');
    var cant = parseFloat(tr.querySelector('.item-cant').value) || 0;
    var pu   = parseFloat(tr.querySelector('.item-pu').value)   || 0;
    var dto  = parseFloat(tr.querySelector('.item-dto').value)  || 0;
    var total = cant * pu * (1 - dto / 100);
    tr.querySelector('.item-total').textContent = '$ ' + total.toFixed(2);
    var seccionDiv = tr.closest('.seccion-disciplina');
    recalcularSeccion(seccionDiv);
}
```

### 4.9 `recalcularSeccion(seccionDiv)`

```javascript
function recalcularSeccion(seccionDiv) {
    var totals = seccionDiv.querySelectorAll('.item-total');
    var sum = 0;
    totals.forEach(function(el) {
        sum += parseFloat(el.textContent.replace('$', '').trim()) || 0;
    });
    seccionDiv.querySelector('.seccion-subtotal').textContent = '$ ' + sum.toFixed(2);
    seccionDiv.querySelector('.seccion-total').textContent = '$ ' + sum.toFixed(2);
    recalcularTotalGeneral();
}
```

### 4.10 `recalcularTotalGeneral()`

```javascript
function recalcularTotalGeneral() {
    var subtotals = document.querySelectorAll('.seccion-subtotal');
    var sum = 0;
    subtotals.forEach(function(el) {
        sum += parseFloat(el.textContent.replace('$', '').trim()) || 0;
    });
    document.getElementById('total-general').textContent = '$ ' + sum.toFixed(2);
}
```

### 4.11 `actualizarIndicesSeccion(tbody)`

```javascript
function actualizarIndicesSeccion(tbody) {
    var rows = tbody.querySelectorAll('tr');
    rows.forEach(function(tr, i) {
        tr.querySelector('.item-idx').textContent = i + 1;
    });
}
```

### 4.12 `cargarPredefinidosEnSeccion(btn)`

```javascript
function cargarPredefinidosEnSeccion(btn) {
    var seccionDiv = btn.closest('.seccion-disciplina');
    var disciplinaId = seccionDiv.dataset.disciplinaId;
    var url = API_ITEMS_URL.replace('/0/', '/' + disciplinaId + '/');
    fetch(url)
        .then(function(r) { return r.json(); })
        .then(function(items) {
            if (!items.length) {
                alert('No hay ítems predefinidos para esta disciplina.');
                return;
            }
            var tbody = seccionDiv.querySelector('.seccion-items-body');
            items.forEach(function(item) {
                var tr = document.createElement('tr');
                var idx = tbody.children.length + 1;
                tr.innerHTML = buildItemRowHTML(idx, item.descripcion, item.unidad_medida, 1, item.precio_unitario, 0, item.id);
                tbody.appendChild(tr);
            });
            actualizarIndicesSeccion(tbody);
            recalcularSeccion(seccionDiv);
        })
        .catch(function(e) { alert('Error al cargar ítems: ' + e.message); });
}
```

### 4.13 `recolectarTodosLosItems()`

```javascript
function recolectarTodosLosItems() {
    var items = [];
    document.querySelectorAll('.seccion-disciplina').forEach(function(seccionDiv) {
        var disciplinaId = seccionDiv.dataset.disciplinaId || null;
        seccionDiv.querySelectorAll('.seccion-items-body tr').forEach(function(tr) {
            items.push({
                disciplina_id: disciplinaId ? parseInt(disciplinaId) : null,
                item_predefinido_id: tr.querySelector('.item-predefinido-id').value || null,
                descripcion: tr.querySelector('.item-desc').value,
                unidad_medida: tr.querySelector('.item-um').value,
                cantidad: parseFloat(tr.querySelector('.item-cant').value) || 0,
                precio_unitario: parseFloat(tr.querySelector('.item-pu').value) || 0,
                descuento_porcentaje: parseFloat(tr.querySelector('.item-dto').value) || 0,
            });
        });
    });
    return items;
}
```

### 4.14 Actualizar `antesDeCrear` y `guardarItems`

```javascript
function antesDeCrear(e) {
    var items = recolectarTodosLosItems();
    document.getElementById('items-json').value = JSON.stringify(items);
}

function guardarItems() {
    var items = recolectarTodosLosItems();
    document.getElementById('items-json').value = JSON.stringify(items);
    document.getElementById('items-form').submit();
}
```

### 4.15 Reconstrucción en modo edición (`DOMContentLoaded`)

```javascript
document.addEventListener('DOMContentLoaded', function() {
    recalcularTotalGeneral();

    // Reconstruir secciones en modo edición
    if (typeof ITEMS_POR_DISCIPLINA !== 'undefined' && ITEMS_POR_DISCIPLINA.length) {
        ITEMS_POR_DISCIPLINA.forEach(function(seccion) {
            var div = agregarSeccion(seccion.disciplina_id, seccion.disciplina_nombre);
            if (!div) return;
            var tbody = div.querySelector('.seccion-items-body');
            seccion.items.forEach(function(item, i) {
                var tr = document.createElement('tr');
                tr.innerHTML = buildItemRowHTML(
                    i + 1,
                    item.descripcion,
                    item.unidad_medida,
                    item.cantidad,
                    item.precio_unitario,
                    item.descuento_porcentaje,
                    item.item_predefinido_id
                );
                tbody.appendChild(tr);
            });
            actualizarIndicesSeccion(tbody);
            recalcularSeccion(div);
        });
    }
});
```

### 4.16 Código obsoleto a eliminar

| Elemento | Razón |
|---|---|
| `var DISCIPLINA_ID = ...` | Reemplazado por `data-disciplina-id` en cada sección |
| `function cargarPredefinidos()` | Reemplazada por `cargarPredefinidosEnSeccion()` |
| `function agregarVacio()` | Reemplazada por `agregarItemEnSeccion()` |
| `function recolectarItems()` | Reemplazada por `recolectarTodosLosItems()` |
| `function recalcularItem()` | Reemplazada por `recalcularItemEnSeccion()` |
| `function recalcularTotal()` | Reemplazada por `recalcularTotalGeneral()` |
| `function actualizarIndices()` | Reemplazada por `actualizarIndicesSeccion()` |
| listener `onchange` de `#disciplina-encabezado` | El select ya no existe |
| `#items-body`, `#items-table` globales | Cada sección tiene su propio `tbody.seccion-items-body` |

---

## 5. Flujo de Datos — Creación

```
Usuario                  Browser                        Django View
   |                        |                               |
   |--- Llena encabezado -->|                               |
   |--- Agrega secciones -->| agregarSeccion()              |
   |--- Agrega ítems ------>| agregarItemEnSeccion()        |
   |--- Click "Crear" ----->| antesDeCrear()                |
   |                        | recolectarTodosLosItems()     |
   |                        | items-json = JSON.stringify() |
   |                        |---- POST /crear_cotizacion -->|
   |                        |     items=[{disciplina_id,.}] |
   |                        |               crear_cotizacion()
   |                        |               Cotizacion(disciplina=None)
   |                        |               ItemCotizacion(disciplina_id=item['disciplina_id'])
   |                        |<--- redirect ver_cotizacion --|
```

## 6. Flujo de Datos — Edición

```
Django View               Browser                        Browser
   |                        |                               |
editar_cotizacion GET:      |                               |
items_por_disciplina_json   |                               |
   |---- render() -------->|                               |
   |                        | DOMContentLoaded              |
   |                        | ITEMS_POR_DISCIPLINA.forEach  |
   |                        | agregarSeccion() × N          |
   |                        | buildItemRowHTML() × M        |
   |                        |                               |
   |                        |--- Usuario edita items ------>|
   |                        |--- Click "Guardar Items" ---->|
   |                        | guardarItems()                |
   |                        | recolectarTodosLosItems()     |
   |                        |--- POST accion=guardar_items->|
   |                        |                          editar_cotizacion()
   |                        |                          items.all().delete()
   |                        |                          ItemCotizacion(disciplina_id=item['disciplina_id'])
```

## 7. API Endpoint (sin cambios)

`GET /presupuestos/api/items-por-disciplina/<disciplina_id>/`

Respuesta:
```json
[
  {
    "id": 42,
    "codigo": "EL-001",
    "descripcion": "Cable 2.5mm²",
    "unidad_medida": "ml",
    "precio_unitario": 1250.00,
    "moneda": "ARS"
  }
]
```

No requiere cambios. La función `cargarPredefinidosEnSeccion()` usa este endpoint pasando el `disciplina_id` de la sección.

## 8. Consideraciones de Compatibilidad

- **Cotizaciones existentes:** Al migrar, los registros existentes conservan su `disciplina_id` original. En modo edición, si la cotización tiene `disciplina != None`, los ítems que no tienen `ItemCotizacion.disciplina` (null) aparecerán agrupados bajo "Sin disciplina".
- **Requisito 8.3:** Ítems con `disciplina=None` se agrupan en una sección "Sin disciplina" con `disciplina_id = null`. El JS debe manejar este caso al reconstruir (clave `null` en el dict).
- **Vista `lista_cotizaciones`:** El filtro por disciplina en la lista puede quedar como está o adaptarse para filtrar por `items__disciplina`; está fuera del scope de este feature.


## 9. Archivos Modificados

| Archivo | Tipo de cambio |
|---|---|
| `presupuestos/models.py` | Modificar campo `Cotizacion.disciplina` → nullable |
| `presupuestos/migrations/XXXX_cotizacion_disciplina_nullable.py` | Crear |
| `presupuestos/views.py` | Modificar `crear_cotizacion`, `editar_cotizacion` |
| `presupuestos/templates/presupuestos/form_cotizacion.html` | Reescribir sección de items + JS |


---

## Error Handling

| Escenario | Comportamiento esperado |
|---|---|
| `crear_cotizacion` POST sin `fecha` | `messages.error` + redirect a formulario de creación |
| `agregarSeccion` con disciplina duplicada | `alert()` en el cliente; no crea sección |
| `agregarSeccionDesdeSelector` sin selección | `alert()` pidiendo seleccionar disciplina |
| `cargarPredefinidosEnSeccion` — API retorna lista vacía | `alert()` informando que no hay ítems predefinidos para la disciplina |
| `cargarPredefinidosEnSeccion` — error de red / 500 | `alert('Error al cargar ítems: ' + e.message)` |
| Migración con datos existentes | `AlterField` en SQL es `ALTER COLUMN ... DROP NOT NULL`; los valores existentes se conservan |
| `ItemCotizacion.disciplina = None` en modo edición | Se agrupa bajo sección "Sin disciplina" (`disciplina_id: null`) |

---

## Testing Strategy

### Tests de modelo
- `Cotizacion.objects.create(numero=..., fecha=..., creado_por=...)` sin `disciplina` → no debe lanzar `IntegrityError`
- `str(cotizacion_sin_disciplina)` → debe retornar `"COT-XXXX-0001 - Sin disciplina"`

### Tests de vista
- POST a `crear_cotizacion` con JSON `[{disciplina_id: 3, ...}]` → `ItemCotizacion.disciplina_id == 3`
- POST `guardar_cabecera` → `cotizacion.disciplina` no se modifica
- POST `guardar_items` con JSON `[{disciplina_id: 3, ...}, {disciplina_id: null, ...}]` → items con `disciplina_id` correcto
- GET `editar_cotizacion` → contexto contiene `items_por_disciplina_json` parseeable

### Tests de integración (manual / Selenium opcional)
- Crear cotización con 2 secciones distintas → POST correcto → ver_cotizacion muestra los ítems
- Editar cotización → secciones reconstruidas correctamente → modificar un ítem → guardar → verificar persistencia



---

## Correctness Properties

### Property 1: Invariante de disciplina por ítem
Todo `ItemCotizacion` guardado a través del nuevo flujo tiene `disciplina_id` igual al `data-disciplina-id` de la sección donde fue creado.

**Validates: Requirements 8.1, 10.1**

### Property 2: Invariante de subtotal de sección
El subtotal mostrado en `.seccion-subtotal` es siempre igual a `sum(cantidad × precio_unitario × (1 − descuento/100))` para todos los ítems de esa sección.

**Validates: Requirements 6.2, 6.4**

### Property 3: Invariante de total general
El valor de `#total-general` es siempre igual a la suma de todos los `.seccion-subtotal` del DOM.

**Validates: Requirements 2.4, 6.3**

### Property 4: Unicidad de sección por disciplina
No pueden coexistir dos elementos `.seccion-disciplina` con el mismo `data-disciplina-id` en el DOM en ningún momento.

**Validates: Requirements 3.4**

### Property 5: Completitud de serialización
`recolectarTodosLosItems()` retorna exactamente N objetos, donde N es el número total de filas `<tr>` visibles en todos los `.seccion-items-body`.

**Validates: Requirements 10.1, 10.2**

### Property 6: Cotizacion nullable sin error de integridad
Crear o guardar una `Cotizacion` con `disciplina=None` no genera ningún error de integridad ni de validación en la base de datos.

**Validates: Requirements 7.1, 7.3, 1.3**
