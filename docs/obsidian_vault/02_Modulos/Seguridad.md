# 📂 Módulo: Seguridad Industrial y Permisos de Trabajo (`seguridad`)

> [!INFO]
> **Etiquetas**: #django/app #seguridad 
> **Propósito**: Seguridad
> **Ubicación en Código**: `file:///d:/Apps/energia/energy/seguridad`

---

## 📦 Modelos de Datos (Base de Datos)

Este módulo gestiona los siguientes modelos en la base de datos. Los campos ForeignKey y relaciones ManyToMany se representan con enlaces `[[ModelName]]` para navegar interactivamente en Obsidian.

### 🗂️ Modelo `[[TipoIncidente]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | nombre |
| `descripcion` | `TextField` | - | descripcion |


### 🗂️ Modelo `[[Incidente]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `titulo` | `CharField` | - | titulo |
| `tipo` | `ForeignKey` | `ForeignKey` ➡️ [[TipoIncidente]] | tipo |
| `descripcion` | `TextField` | - | descripcion |
| `fecha_ocurrencia` | `DateTimeField` | - | fecha ocurrencia |
| `ubicacion` | `ForeignKey` | `ForeignKey` ➡️ [[Ubicacion]] | ubicacion |
| `ubicacion_texto` | `CharField` | - | ubicacion texto (Descripción manual si no hay ubicación registrada) |
| `reportado_por` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | reportado por |
| `severidad` | `CharField` | - | severidad |
| `estado` | `CharField` | - | estado |
| `foto` | `FileField` | - | foto |
| `fecha_reporte` | `DateTimeField` | - | fecha reporte |
| `fecha_cierre` | `DateTimeField` | - | fecha cierre |


### 🗂️ Modelo `[[TipoInspeccion]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | nombre |
| `descripcion` | `TextField` | - | descripcion |


### 🗂️ Modelo `[[ItemInspeccion]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `tipo_inspeccion` | `ForeignKey` | `ForeignKey` ➡️ [[TipoInspeccion]] | tipo inspeccion |
| `texto` | `CharField` | - | texto |
| `orden` | `PositiveIntegerField` | - | orden |


### 🗂️ Modelo `[[Inspeccion]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `tipo` | `ForeignKey` | `ForeignKey` ➡️ [[TipoInspeccion]] | tipo |
| `fecha` | `DateTimeField` | - | fecha |
| `inspector` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | inspector |
| `ubicacion` | `ForeignKey` | `ForeignKey` ➡️ [[Ubicacion]] | ubicacion |
| `activo` | `ForeignKey` | `ForeignKey` ➡️ [[Activo]] | activo |
| `resultado_global` | `CharField` | - | resultado global |
| `comentarios` | `TextField` | - | comentarios |


### 🗂️ Modelo `[[ResultadoInspeccion]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `inspeccion` | `ForeignKey` | `ForeignKey` ➡️ [[Inspeccion]] | inspeccion |
| `item` | `ForeignKey` | `ForeignKey` ➡️ [[ItemInspeccion]] | item |
| `estado` | `CharField` | - | estado |
| `observacion` | `CharField` | - | observacion |
| `foto` | `FileField` | - | foto |


### 🗂️ Modelo `[[AsignacionEPP]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `miembro` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | miembro |
| `material` | `ForeignKey` | `ForeignKey` ➡️ [[Material]] | material (Debe ser un material de categoría EPP) |
| `cantidad` | `DecimalField` | - | cantidad |
| `fecha_entrega` | `DateTimeField` | - | fecha entrega |
| `motivo` | `CharField` | - | motivo |
| `fecha_proxima_entrega` | `DateField` | - | fecha proxima entrega (Fecha sugerida para renovación) |
| `entregado_por` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | entregado por |


### 🗂️ Modelo `[[PeligroCatalogo]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | nombre |
| `descripcion` | `TextField` | - | descripcion |
| `categoria` | `CharField` | - | categoria |


### 🗂️ Modelo `[[MedidaControlCatalogo]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | nombre |
| `descripcion` | `TextField` | - | descripcion |
| `tipo` | `CharField` | - | tipo |
| `peligros_asociados` | `ManyToManyField` | `ManyToManyField` ➡️ [[PeligroCatalogo]] | peligros asociados |


### 🗂️ Modelo `[[AnalisisRiesgo]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `fecha` | `DateTimeField` | - | fecha |
| `ubicacion` | `ForeignKey` | `ForeignKey` ➡️ [[Ubicacion]] | ubicacion |
| `descripcion_trabajo` | `TextField` | - | Descripción del Trabajo |
| `lider` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | Líder del Trabajo |
| `firmado` | `BooleanField` | - | firmado |
| `orden_trabajo` | `ForeignKey` | `ForeignKey` ➡️ [[OrdenTrabajo]] | orden trabajo |
| `ejecutantes` | `ManyToManyField` | `ManyToManyField` ➡️ [[User]] | ejecutantes |


### 🗂️ Modelo `[[PasoTrabajo]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `analisis` | `ForeignKey` | `ForeignKey` ➡️ [[AnalisisRiesgo]] | analisis |
| `descripcion` | `CharField` | - | descripcion |
| `orden` | `PositiveIntegerField` | - | orden |


### 🗂️ Modelo `[[Riesgo]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `paso` | `ForeignKey` | `ForeignKey` ➡️ [[PasoTrabajo]] | paso |
| `peligro_base` | `ForeignKey` | `ForeignKey` ➡️ [[PeligroCatalogo]] | peligro base |
| `descripcion` | `CharField` | - | Peligro/Riesgo (Manual) |
| `probabilidad` | `IntegerField` | - | probabilidad |
| `consecuencia` | `IntegerField` | - | consecuencia |


### 🗂️ Modelo `[[Control]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `riesgo` | `ForeignKey` | `ForeignKey` ➡️ [[Riesgo]] | riesgo |
| `control_base` | `ForeignKey` | `ForeignKey` ➡️ [[MedidaControlCatalogo]] | control base |
| `descripcion` | `CharField` | - | Medida de Control (Manual) |
| `verificado` | `BooleanField` | - | ¿Control Implementado? |


### 🗂️ Modelo `[[TipoPermiso]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | nombre |
| `descripcion` | `TextField` | - | descripcion |


### 🗂️ Modelo `[[RequisitoPermiso]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `tipo_permiso` | `ForeignKey` | `ForeignKey` ➡️ [[TipoPermiso]] | tipo permiso |
| `texto` | `CharField` | - | texto |
| `es_critico` | `BooleanField` | - | es critico (Si es crítico, no se puede proceder sin este requisito) |
| `orden` | `PositiveIntegerField` | - | orden |
| `tipo_respuesta` | `CharField` | - | tipo respuesta |
| `verificacion` | `CharField` | - | verificacion (¿Qué debe verificar el solicitante/autorizador?) |
| `unidad_medida` | `CharField` | - | unidad medida (Ej: ppm, %, LEL) |
| `valor_objetivo` | `FloatField` | - | valor objetivo (Valor ideal esperado) |
| `rango_min` | `FloatField` | - | rango min |
| `rango_max` | `FloatField` | - | rango max |
| `tabla_relacionada` | `CharField` | - | tabla relacionada (Modelo relacionado si el tipo es TABLA (ej: auth.User, activos.Activo)) |
| `depende_de` | `ForeignKey` | `ForeignKey` ➡️ [[RequisitoPermiso]] | depende de (Si se define, este requisito solo se muestra si la condición del requisito padre se cumple) |
| `depende_condicion` | `CharField` | - | depende condicion (Condición sobre el requisito padre para mostrar este) |


### 🗂️ Modelo `[[PermisoTrabajo]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `tipo` | `ForeignKey` | `ForeignKey` ➡️ [[TipoPermiso]] | tipo |
| `ubicacion` | `ForeignKey` | `ForeignKey` ➡️ [[Ubicacion]] | ubicacion |
| `descripcion_trabajo` | `TextField` | - | descripcion trabajo |
| `fecha_inicio` | `DateTimeField` | - | fecha inicio |
| `fecha_fin` | `DateTimeField` | - | fecha fin |
| `solicitante` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | solicitante |
| `autorizado_por` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | autorizado por |
| `fecha_autorizacion` | `DateTimeField` | - | fecha autorizacion |
| `estado` | `CharField` | - | estado |
| `ast_vinculado` | `ForeignKey` | `ForeignKey` ➡️ [[AnalisisRiesgo]] | AST Vinculado |
| `orden_trabajo` | `ForeignKey` | `ForeignKey` ➡️ [[OrdenTrabajo]] | Orden de Trabajo |


### 🗂️ Modelo `[[VerificacionRequisito]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `permiso` | `ForeignKey` | `ForeignKey` ➡️ [[PermisoTrabajo]] | permiso |
| `requisito` | `ForeignKey` | `ForeignKey` ➡️ [[RequisitoPermiso]] | requisito |
| `valor_texto` | `TextField` | - | valor texto |
| `valor_numerico` | `FloatField` | - | valor numerico |
| `valor_bool` | `BooleanField` | - | valor bool (Para tipos CHECK) |
| `no_aplica` | `BooleanField` | - | no aplica |
| `comentarios` | `TextField` | - | comentarios (Observaciones adicionales) |
| `foto` | `FileField` | - | foto |
| `capturado_por` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | capturado por |
| `creado_en` | `DateTimeField` | - | creado en |


### 🗂️ Modelo `[[ObjetoCatalogo]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | nombre |
| `descripcion` | `TextField` | - | descripcion |


### 🗂️ Modelo `[[LevantamientoConfiscacion]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `fecha` | `DateTimeField` | - | fecha |
| `ubicacion` | `ForeignKey` | `ForeignKey` ➡️ [[Ubicacion]] | Ubicación |
| `inspector` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | inspector |
| `comentarios` | `TextField` | - | comentarios |
| `folio` | `CharField` | - | folio |
| `finalizado` | `BooleanField` | - | ¿Finalizado? |
| `fecha_fin` | `DateTimeField` | - | Fecha de Finalización |


### 🗂️ Modelo `[[EntregaConfiscacion]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre_retirante` | `CharField` | - | Nombre de quien recibe |
| `dni_retirante` | `CharField` | - | DNI/Identidad |
| `foto_identidad` | `FileField` | - | foto identidad |
| `foto_entrega` | `FileField` | - | foto entrega |
| `entregado_por` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | entregado por |
| `fecha` | `DateTimeField` | - | fecha |
| `comentarios` | `TextField` | - | comentarios |


### 🗂️ Modelo `[[ObjetoConfiscado]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `levantamiento` | `ForeignKey` | `ForeignKey` ➡️ [[LevantamientoConfiscacion]] | levantamiento |
| `catalogo_objeto` | `ForeignKey` | `ForeignKey` ➡️ [[ObjetoCatalogo]] | Tipo de Objeto |
| `codigo_barras` | `CharField` | - | Código de Barras/Etiqueta |
| `descripcion` | `TextField` | - | descripcion |
| `ubicacion_especifica` | `CharField` | - | Ubicación Específica |
| `status` | `CharField` | - | status |
| `fecha_confiscacion` | `DateTimeField` | - | fecha confiscacion |
| `fecha_retiro` | `DateTimeField` | - | fecha retiro |
| `entrega` | `ForeignKey` | `ForeignKey` ➡️ [[EntregaConfiscacion]] | entrega |
| `comentario_almacen` | `TextField` | - | Comentario de Almacén/Discrepancia |
| `ubicacion_almacen` | `CharField` | - | Ubicación en Bodega |


### 🗂️ Modelo `[[FotoObjetoConfiscado]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `objeto` | `ForeignKey` | `ForeignKey` ➡️ [[ObjetoConfiscado]] | objeto |
| `foto` | `FileField` | - | foto |
| `etapa` | `CharField` | - | etapa |
| `creado_en` | `DateTimeField` | - | creado en |



---
🔙 Volver a [[00_Inicio|Inicio]]