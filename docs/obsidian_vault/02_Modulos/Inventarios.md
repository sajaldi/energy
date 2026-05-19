# 📂 Módulo: Inventarios y Materiales (`inventarios`)

> [!INFO]
> **Etiquetas**: #django/app #inventarios 
> **Propósito**: Inventarios
> **Ubicación en Código**: `file:///d:/Apps/energia/energy/inventarios`

---

## 📦 Modelos de Datos (Base de Datos)

Este módulo gestiona los siguientes modelos en la base de datos. Los campos ForeignKey y relaciones ManyToMany se representan con enlaces `[[ModelName]]` para navegar interactivamente en Obsidian.

### 🗂️ Modelo `[[SolicitudMaterial]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `usuario` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | usuario |
| `fecha_solicitud` | `DateTimeField` | - | fecha solicitud |
| `estado` | `CharField` | - | estado |
| `orden_trabajo` | `ForeignKey` | `ForeignKey` ➡️ [[OrdenTrabajo]] | orden trabajo |
| `ubicacion_origen` | `ForeignKey` | `ForeignKey` ➡️ [[Ubicacion]] | ubicacion origen |
| `edificio_destino` | `ForeignKey` | `ForeignKey` ➡️ [[Ubicacion]] | Edificio Destino |
| `nivel_destino` | `ForeignKey` | `ForeignKey` ➡️ [[Ubicacion]] | Nivel Destino |
| `comentarios_solicitud` | `TextField` | - | comentarios solicitud |
| `comentarios_almacen` | `TextField` | - | comentarios almacen |
| `fecha_entrega` | `DateTimeField` | - | fecha entrega |
| `entregado_por` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | entregado por |


### 🗂️ Modelo `[[CategoriaMaterial]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | Nombre de la Categoría |
| `padre` | `ForeignKey` | `ForeignKey` ➡️ [[CategoriaMaterial]] | Categoría Padre |
| `descripcion` | `TextField` | - | Descripción |


### 🗂️ Modelo `[[UnidadMedida]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | Nombre de la Unidad |
| `abreviatura` | `CharField` | - | Abreviatura |


### 🗂️ Modelo `[[Material]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | Nombre del Material |
| `sku` | `CharField` | - | SKU / Código Interno |
| `marca` | `ForeignKey` | `ForeignKey` ➡️ [[Marca]] | Marca |
| `descripcion` | `TextField` | - | Descripción |
| `categoria` | `ForeignKey` | `ForeignKey` ➡️ [[CategoriaMaterial]] | Categoría |
| `unidad_medida` | `ForeignKey` | `ForeignKey` ➡️ [[UnidadMedida]] | Unidad de Medida |
| `precio_estimado` | `DecimalField` | - | precio estimado |
| `stock_minimo` | `DecimalField` | - | stock minimo (Alerta cuando el stock total baje de este nivel) |
| `tipo_material` | `CharField` | - | Tipo de Material |
| `imagen` | `FileField` | - | Imagen del Material |
| `creado_en` | `DateTimeField` | - | creado en |
| `actualizado_en` | `DateTimeField` | - | actualizado en |
| `departamentos` | `ManyToManyField` | `ManyToManyField` ➡️ [[Departamento]] | Departamentos Permitidos (Si se seleccionan departamentos, solo los usuarios de estos departamentos podrán utilizar este material. Si está vacío, cualquier usuario podrá utilizarlo (Global).) |


### 🗂️ Modelo `[[FotoMaterial]]`

> **Descripción**: Permite asociar múltiples fotos a un solo material (ej. placa, estado, empaque).

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `material` | `ForeignKey` | `ForeignKey` ➡️ [[Material]] | Material |
| `imagen` | `FileField` | - | Imagen |
| `fecha_creacion` | `DateTimeField` | - | fecha creacion |


### 🗂️ Modelo `[[CompatibilidadMaterial]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `material` | `ForeignKey` | `ForeignKey` ➡️ [[Material]] | material |
| `modelo` | `ForeignKey` | `ForeignKey` ➡️ [[Modelo]] | modelo |
| `cantidad_sugerida` | `DecimalField` | - | cantidad sugerida (Cantidad usual requerida para este modelo) |
| `notas` | `CharField` | - | notas |


### 🗂️ Modelo `[[Lote]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `material` | `ForeignKey` | `ForeignKey` ➡️ [[Material]] | material |
| `codigo` | `CharField` | - | Código de Lote |
| `fecha_vencimiento` | `DateField` | - | Fecha de Vencimiento |
| `fecha_fabricacion` | `DateField` | - | Fecha de Fabricación |
| `creado_en` | `DateTimeField` | - | creado en |


### 🗂️ Modelo `[[IngresoInventario]]`

> **Descripción**: Agrupa un conjunto de materiales que entran al inventario en un mismo momento.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `usuario` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | Recibido por |
| `fecha_ingreso` | `DateTimeField` | - | Fecha de Ingreso |
| `ubicacion_destino` | `ForeignKey` | `ForeignKey` ➡️ [[Ubicacion]] | ubicacion destino |
| `requisicion_origen` | `ForeignKey` | `ForeignKey` ➡️ [[Requisicion]] | requisicion origen |
| `comentarios` | `TextField` | - | comentarios |


### 🗂️ Modelo `[[FotoIngreso]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `ingreso` | `ForeignKey` | `ForeignKey` ➡️ [[IngresoInventario]] | Ingreso |
| `imagen` | `FileField` | - | Foto del Ingreso |
| `fecha_creacion` | `DateTimeField` | - | fecha creacion |


### 🗂️ Modelo `[[FotoDespacho]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `solicitud` | `ForeignKey` | `ForeignKey` ➡️ [[SolicitudMaterial]] | Solicitud |
| `imagen` | `FileField` | - | Foto del Despacho |
| `fecha_creacion` | `DateTimeField` | - | fecha creacion |


### 🗂️ Modelo `[[StockRecord]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `material` | `ForeignKey` | `ForeignKey` ➡️ [[Material]] | material |
| `lote` | `ForeignKey` | `ForeignKey` ➡️ [[Lote]] | lote |
| `ubicacion` | `ForeignKey` | `ForeignKey` ➡️ [[Ubicacion]] | ubicacion |
| `cantidad` | `DecimalField` | - | cantidad |
| `ubicacion_especifica` | `CharField` | - | Ubicación Específica (Pasillo/Estante) |
| `actualizado_en` | `DateTimeField` | - | actualizado en |


### 🗂️ Modelo `[[MovimientoInventario]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `material` | `ForeignKey` | `ForeignKey` ➡️ [[Material]] | material |
| `lote` | `ForeignKey` | `ForeignKey` ➡️ [[Lote]] | lote |
| `solicitud` | `ForeignKey` | `ForeignKey` ➡️ [[SolicitudMaterial]] | solicitud |
| `ingreso` | `ForeignKey` | `ForeignKey` ➡️ [[IngresoInventario]] | Ingreso relacionado |
| `devolucion` | `ForeignKey` | `ForeignKey` ➡️ [[DevolucionMaterial]] | Devolución relacionada |
| `tipo` | `CharField` | - | tipo |
| `cantidad` | `DecimalField` | - | Cantidad Entregada/Real |
| `cantidad_solicitada` | `DecimalField` | - | Cantidad Solicitada |
| `ubicacion_origen` | `ForeignKey` | `ForeignKey` ➡️ [[Ubicacion]] | ubicacion origen |
| `ubicacion_destino` | `ForeignKey` | `ForeignKey` ➡️ [[Ubicacion]] | ubicacion destino |
| `ubicacion_especifica` | `CharField` | - | Ubicación Específica (Destino) |
| `orden_trabajo` | `ForeignKey` | `ForeignKey` ➡️ [[OrdenTrabajo]] | orden trabajo |
| `usuario` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | usuario |
| `comentarios` | `TextField` | - | comentarios |
| `fecha_movimiento` | `DateTimeField` | - | fecha movimiento |
| `es_inconsistente` | `BooleanField` | - | Inconsistente (Sin Stock) |
| `estado` | `CharField` | - | estado |
| `aprobado_por` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | aprobado por |
| `fecha_aprobacion` | `DateTimeField` | - | fecha aprobacion |


### 🗂️ Modelo `[[DevolucionMaterial]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `usuario_recibe` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | Recibido por |
| `persona_devuelve` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | Persona que Devuelve |
| `fecha_devolucion` | `DateTimeField` | - | Fecha de Devolución |
| `ubicacion_destino` | `ForeignKey` | `ForeignKey` ➡️ [[Ubicacion]] | Ubicación de Destino |
| `comentarios` | `TextField` | - | Comentarios / Observaciones |


### 🗂️ Modelo `[[ItemDevolucion]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `devolucion` | `ForeignKey` | `ForeignKey` ➡️ [[DevolucionMaterial]] | devolucion |
| `material_original` | `ForeignKey` | `ForeignKey` ➡️ [[Material]] | material original |
| `material_recibido` | `ForeignKey` | `ForeignKey` ➡️ [[Material]] | material recibido |
| `cantidad` | `DecimalField` | - | cantidad |
| `estado_fisico` | `CharField` | - | estado fisico |


### 🗂️ Modelo `[[FotoDevolucion]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `devolucion` | `ForeignKey` | `ForeignKey` ➡️ [[DevolucionMaterial]] | devolucion |
| `imagen` | `FileField` | - | imagen |
| `creado_en` | `DateTimeField` | - | creado en |



---
🔙 Volver a [[00_Inicio|Inicio]]