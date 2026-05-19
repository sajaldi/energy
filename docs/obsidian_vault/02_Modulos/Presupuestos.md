# 📂 Módulo: Gestión Presupuestaria y Requisiciones (`presupuestos`)

> [!INFO]
> **Etiquetas**: #django/app #presupuestos 
> **Propósito**: Presupuestos
> **Ubicación en Código**: `file:///d:/Apps/energia/energy/presupuestos`

---

## 📦 Modelos de Datos (Base de Datos)

Este módulo gestiona los siguientes modelos en la base de datos. Los campos ForeignKey y relaciones ManyToMany se representan con enlaces `[[ModelName]]` para navegar interactivamente en Obsidian.

### 🗂️ Modelo `[[PresupuestoAnual]]`

> **Descripción**: Plan financiero anual global.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | Nombre del Plan |
| `anio` | `PositiveIntegerField` | - | Año |
| `moneda` | `CharField` | - | moneda |
| `estado` | `CharField` | - | estado |
| `descripcion` | `TextField` | - | Descripción / Notas |
| `elaborado_por` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | elaborado por |
| `creado_en` | `DateTimeField` | - | creado en |
| `actualizado_en` | `DateTimeField` | - | actualizado en |


### 🗂️ Modelo `[[PartidaPresupuestaria]]`

> **Descripción**: Asignación presupuestaria para una Disciplina específica dentro de un año.
    Ahora actúa como la fila principal de la Cost Sheet.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `presupuesto_anual` | `ForeignKey` | `ForeignKey` ➡️ [[PresupuestoAnual]] | presupuesto anual |
| `disciplina` | `ForeignKey` | `ForeignKey` ➡️ [[Disciplina]] | Disciplina |
| `monto_proyectado` | `DecimalField` | - | Monto Original (Aprobado) |
| `descripcion` | `CharField` | - | Referencia/Nota |
| `departamentos` | `ManyToManyField` | `ManyToManyField` ➡️ [[Departamento]] | Departamentos Permitidos (Si se seleccionan departamentos, solo los usuarios de estos departamentos verán esta partida. Si está vacío, será visible para todos (Global).) |


### 🗂️ Modelo `[[CambioPresupuesto]]`

> **Descripción**: Gestión de cambios al presupuesto (Transferencias, Adicionales).

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `partida` | `ForeignKey` | `ForeignKey` ➡️ [[PartidaPresupuestaria]] | partida |
| `monto` | `DecimalField` | - | monto (Use negativo para reducciones) |
| `tipo` | `CharField` | - | tipo |
| `estado` | `CharField` | - | estado |
| `descripcion` | `CharField` | - | descripcion |
| `fecha_solicitud` | `DateField` | - | fecha solicitud |
| `fecha_aprobacion` | `DateField` | - | fecha aprobacion |
| `creado_en` | `DateTimeField` | - | creado en |


### 🗂️ Modelo `[[Compromiso]]`

> **Descripción**: Representa un Contrato, Orden de Compra o Compromiso Directo.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `descripcion` | `CharField` | - | Descripción del Contrato/OC |
| `proveedor` | `CharField` | - | Proveedor / Contratista |
| `referencia` | `CharField` | - | N° Referencia (OC/Contrato) |
| `fecha` | `DateField` | - | fecha |
| `monto_total` | `DecimalField` | - | monto total |
| `estado` | `CharField` | - | estado |
| `creado_en` | `DateTimeField` | - | creado en |
| `actualizado_en` | `DateTimeField` | - | actualizado en |


### 🗂️ Modelo `[[DetalleCompromiso]]`

> **Descripción**: Línea de detalle de un compromiso que afecta a una partida específica.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `compromiso` | `ForeignKey` | `ForeignKey` ➡️ [[Compromiso]] | compromiso |
| `partida` | `ForeignKey` | `ForeignKey` ➡️ [[PartidaPresupuestaria]] | partida |
| `monto_comprometido` | `DecimalField` | - | monto comprometido |
| `descripcion` | `CharField` | - | descripcion |


### 🗂️ Modelo `[[GastoEjecutado]]`

> **Descripción**: Registro manual de gastos (Facturas, Pagos).
    Puede estar vinculado a un Compromiso previo o ser directo.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `partida` | `ForeignKey` | `ForeignKey` ➡️ [[PartidaPresupuestaria]] | partida |
| `compromiso` | `ForeignKey` | `ForeignKey` ➡️ [[Compromiso]] | Compromiso Relacionado |
| `fecha` | `DateField` | - | fecha |
| `monto` | `DecimalField` | - | monto |
| `descripcion` | `CharField` | - | Concepto de Gasto |
| `referencia` | `CharField` | - | referencia (N° de Factura, OC o similar) |
| `creado_en` | `DateTimeField` | - | creado en |


### 🗂️ Modelo `[[ItemPresupuesto]]`

> **Descripción**: Desglose de una partida en conceptos específicos.
    Define la regla de recurrencia (Padre).

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `partida` | `ForeignKey` | `ForeignKey` ➡️ [[PartidaPresupuestaria]] | partida |
| `parent` | `ForeignKey` | `ForeignKey` ➡️ [[ItemPresupuesto]] | Item Padre |
| `concepto` | `CharField` | - | Concepto/Descripción |
| `es_recurrente` | `BooleanField` | - | ¿Es Recurrente? |
| `frecuencia` | `CharField` | - | frecuencia |
| `monto_base` | `DecimalField` | - | monto base (Monto para cada ocurrencia) |
| `mes_inicio` | `PositiveIntegerField` | - | mes inicio (Mes de comienzo (1=Enero, 12=Diciembre)) |


### 🗂️ Modelo `[[DetallePeriodico]]`

> **Descripción**: Hijo de ItemPresupuesto. Guarda el monto específico para un mes.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `item` | `ForeignKey` | `ForeignKey` ➡️ [[ItemPresupuesto]] | item |
| `mes` | `PositiveIntegerField` | - | mes |
| `monto` | `DecimalField` | - | monto |


### 🗂️ Modelo `[[PresupuestoAgrupado]]`

> **Descripción**: Agrupación de varios presupuestos anuales para visualización gerencial.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | Nombre del Grupo |
| `descripcion` | `TextField` | - | Descripción / Notas |
| `anio` | `PositiveIntegerField` | - | Año de Referencia |
| `creado_en` | `DateTimeField` | - | creado en |
| `actualizado_en` | `DateTimeField` | - | actualizado en |
| `presupuestos` | `ManyToManyField` | `ManyToManyField` ➡️ [[PresupuestoAnual]] | Presupuestos Incluidos |


### 🗂️ Modelo `[[Requisicion]]`

> **Descripción**: Modelo para sincronización de Requisiciones desde Dynamics 365.
    Mapea campos de la entidad cr8ca_requisicion.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `cr8ca_requisicionid` | `UUIDField` | - | ID de Requisición (Dynamics) |
| `cr8ca_requisicion` | `CharField` | - | N° Requisición (REQ-#####-AAAA) |
| `cr8ca_asunto` | `CharField` | - | Asunto |
| `cr8ca_motivo` | `TextField` | - | Motivo |
| `cr8ca_comentarios` | `TextField` | - | Comentarios |
| `cr8ca_totalenarticulos` | `DecimalField` | - | Total en Artículos |
| `cr8ca_prioridad` | `IntegerField` | - | Prioridad |
| `cr8ca_id_oc` | `CharField` | - | ID OC (Orden de Compra) |
| `cr8ca_ejecutado` | `BooleanField` | - | cr8ca ejecutado |
| `cr8ca_cerrar` | `BooleanField` | - | cr8ca cerrar |
| `cr8ca_cajachica` | `BooleanField` | - | cr8ca cajachica |
| `cr8ca_solicituddetabladepago` | `BooleanField` | - | cr8ca solicituddetabladepago |
| `cr8ca_seleccionar` | `BooleanField` | - | cr8ca seleccionar |
| `_ownerid_value` | `UUIDField` | - |  ownerid value |
| `fecha` | `DateTimeField` | - | Fecha |
| `fecha_aprobacion` | `DateTimeField` | - | Aprobado el |
| `cr8ca_fechadegasto` | `DateTimeField` | - | cr8ca fechadegasto |
| `createdon` | `DateTimeField` | - | Creado en Dynamics |
| `modifiedon` | `DateTimeField` | - | Modificado en Dynamics |
| `versionnumber` | `BigIntegerField` | - | versionnumber |
| `statecode` | `IntegerField` | - | statecode |
| `statuscode` | `IntegerField` | - | statuscode |
| `estado_requisicion` | `CharField` | - | Estado de la Requisición |
| `wizard_step` | `IntegerField` | - | Paso del Wizard |
| `usuario_solicitante` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | Solicitante |
| `usuario_en_nombre_de` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | En nombre de |
| `partida` | `ForeignKey` | `ForeignKey` ➡️ [[PartidaPresupuestaria]] | Partida Presupuestaria |
| `item_presupuesto` | `ForeignKey` | `ForeignKey` ➡️ [[ItemPresupuesto]] | Ítem de Presupuesto |
| `tipo_rutina` | `ForeignKey` | `ForeignKey` ➡️ [[Tipo]] | Tipo de Rutina |
| `proveedor` | `ForeignKey` | `ForeignKey` ➡️ [[Empresa]] | Proveedor Asignado |
| `proveedores_sugeridos_notas` | `TextField` | - | Detalle por Proveedor (Especifique qué artículos corresponden a cada proveedor sugerido.) |
| `proveedores_sugeridos` | `ManyToManyField` | `ManyToManyField` ➡️ [[Empresa]] | Proveedores Sugeridos |


### 🗂️ Modelo `[[ArticuloRequisicion]]`

> **Descripción**: Artículos individuales dentro de una Requisición.
    Mapea campos de cr8ca_itemderequisicions.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `cr8ca_itemderequisicionid` | `UUIDField` | - | cr8ca itemderequisicionid |
| `requisicion` | `ForeignKey` | `ForeignKey` ➡️ [[Requisicion]] | Requisición |
| `proveedor` | `ForeignKey` | `ForeignKey` ➡️ [[Empresa]] | Proveedor sugerido para este artículo |
| `material` | `ForeignKey` | `ForeignKey` ➡️ [[Material]] | Material vinculado |
| `cr8ca_articulo` | `CharField` | - | Descripción del Artículo |
| `cr8ca_cantidad` | `DecimalField` | - | Cantidad |
| `cr8ca_costoaproximado` | `DecimalField` | - | Costo Aprox. |
| `cr8ca_costoaproximado_base` | `DecimalField` | - | cr8ca costoaproximado base |
| `cr8ca_tipo` | `IntegerField` | - | cr8ca tipo |
| `_cr8ca_edificiozona_value` | `UUIDField` | - |  cr8ca edificiozona value |
| `_cr8ca_activo_value` | `UUIDField` | - |  cr8ca activo value |
| `_cr8ca_catalogo_value` | `UUIDField` | - |  cr8ca catalogo value |
| `_cr8ca_unidad_value` | `UUIDField` | - |  cr8ca unidad value |
| `versionnumber` | `BigIntegerField` | - | versionnumber |
| `createdon` | `DateTimeField` | - | createdon |
| `modifiedon` | `DateTimeField` | - | modifiedon |
| `exchangerate` | `DecimalField` | - | exchangerate |


### 🗂️ Modelo `[[DocumentoRequisicion]]`

> **Descripción**: Documentos adjuntos a una requisición, almacenados en MinIO.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `requisicion` | `ForeignKey` | `ForeignKey` ➡️ [[Requisicion]] | Requisición |
| `archivo` | `FileField` | - | Archivo |
| `nombre` | `CharField` | - | Nombre/Descripción del Documento |
| `creado_en` | `DateTimeField` | - | creado en |


### 🗂️ Modelo `[[SolicitudPago]]`

> **Descripción**: Agrupa varias solicitudes de pago de distintas requisiciones.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `descripcion` | `CharField` | - | Descripción Global/Referencia |
| `fecha_solicitud` | `DateField` | - | Fecha de Solicitud |
| `usuario_solicitante` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | Solicitante |
| `estado` | `CharField` | - | estado |
| `creado_en` | `DateTimeField` | - | creado en |
| `actualizado_en` | `DateTimeField` | - | actualizado en |


### 🗂️ Modelo `[[ItemSolicitudPago]]`

> **Descripción**: Item individual de una solicitud de pago, vinculado a una requisición.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `solicitud` | `ForeignKey` | `ForeignKey` ➡️ [[SolicitudPago]] | Solicitud Padre |
| `requisicion` | `ForeignKey` | `ForeignKey` ➡️ [[Requisicion]] | Requisición Vinculada |
| `monto_solicitado` | `DecimalField` | - | Monto Solicitado |
| `condicion_pago` | `CharField` | - | Condición de Pago |
| `descripcion` | `CharField` | - | Descripción del Pago (Ej: Anticipo, Pago Parcial, Pago Final) |
| `estatus` | `CharField` | - | Estatus del Item |
| `creado_en` | `DateTimeField` | - | creado en |
| `actualizado_en` | `DateTimeField` | - | actualizado en |


### 🗂️ Modelo `[[REPEX]]`

> **Descripción**: Replacement Expenditure - Plan de reposición de activos.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | Nombre del Plan |
| `anio` | `PositiveIntegerField` | - | Año |
| `descripcion` | `TextField` | - | Descripción / Notas |
| `estado` | `CharField` | - | estado |
| `creado_por` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | creado por |
| `creado_en` | `DateTimeField` | - | creado en |
| `actualizado_en` | `DateTimeField` | - | actualizado en |


### 🗂️ Modelo `[[REPEXItem]]`

> **Descripción**: Item individual de un plan REPEX.
    Puede estar vinculado a un activo o ser un ítem manual (ej: reposición masiva).

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `repex` | `ForeignKey` | `ForeignKey` ➡️ [[REPEX]] | repex |
| `activo` | `ForeignKey` | `ForeignKey` ➡️ [[Activo]] | activo (Dejar vacío para ítems manuales) |
| `modelo` | `ForeignKey` | `ForeignKey` ➡️ [[Modelo]] | modelo (Modelo asociado para ítems manuales) |
| `nombre_item` | `CharField` | - | nombre item (Nombre descriptivo cuando no hay activo vinculado) |
| `ubicacion_manual` | `CharField` | - | ubicacion manual (Ubicación manual (ej: Edificio A → Nivel 2)) |
| `categoria_manual` | `CharField` | - | categoria manual (Categoría del ítem (ej: Iluminación, Plomería)) |
| `unidades` | `CharField` | - | unidades (Unidad de medida (ej: pieza, metro, lote)) |
| `cantidad` | `DecimalField` | - | cantidad (Cantidad de unidades) |
| `precio_unitario` | `DecimalField` | - | precio unitario (Precio por unidad) |
| `descripcion` | `CharField` | - | descripcion (Motivo de la reposición) |
| `costo_original` | `DecimalField` | - | costo original (Costo original del sistema) |
| `costo_reposicion` | `DecimalField` | - | costo reposicion (Costo total (cantidad × precio unitario)) |
| `fecha_proyectada` | `DateField` | - | fecha proyectada |
| `prioridad` | `CharField` | - | prioridad |
| `justificacion` | `TextField` | - | justificacion |



---
🔙 Volver a [[00_Inicio|Inicio]]