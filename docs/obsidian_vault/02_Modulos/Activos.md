# 📂 Módulo: Gestión de Activos Industriales (`activos`)

> [!INFO]
> **Etiquetas**: #django/app #activos 
> **Propósito**: Activos
> **Ubicación en Código**: `file:///d:/Apps/energia/energy/activos`

---

## 📦 Modelos de Datos (Base de Datos)

Este módulo gestiona los siguientes modelos en la base de datos. Los campos ForeignKey y relaciones ManyToMany se representan con enlaces `[[ModelName]]` para navegar interactivamente en Obsidian.

### 🗂️ Modelo `[[Disciplina]]`

> **Descripción**: Modelo jerárquico para clasificar planos por especialidad técnica.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | nombre |
| `padre` | `ForeignKey` | `ForeignKey` ➡️ [[Disciplina]] | padre (Disciplina de nivel superior) |
| `descripcion` | `TextField` | - | descripcion |
| `creado_en` | `DateTimeField` | - | creado en |


### 🗂️ Modelo `[[Categoria]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | nombre |
| `padre` | `ForeignKey` | `ForeignKey` ➡️ [[Categoria]] | padre |
| `icono` | `CharField` | - | icono (Nombre del icono de Ionicons (ej: flash, water, construct, bulb)) |
| `descripcion` | `TextField` | - | descripcion |


### 🗂️ Modelo `[[Familia]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | nombre |
| `padre` | `ForeignKey` | `ForeignKey` ➡️ [[Familia]] | padre |
| `descripcion` | `TextField` | - | descripcion |


### 🗂️ Modelo `[[Ubicacion]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | nombre |
| `codigo_qr` | `CharField` | - | codigo qr (Código físico de la ubicación (ej. UBC000000001)) |
| `padre` | `ForeignKey` | `ForeignKey` ➡️ [[Ubicacion]] | padre |
| `tipo` | `CharField` | - | tipo (Tipo de ubicación) |
| `descripcion` | `TextField` | - | descripcion |
| `orden` | `PositiveIntegerField` | - | orden (Orden de visualización y programación) |
| `es_almacen` | `BooleanField` | - | es almacen (Marcar si esta ubicación funciona como bodega/almacén de materiales) |
| `categoria` | `ForeignKey` | `ForeignKey` ➡️ [[Categoria]] | categoria (Categoría asociada para rutinas de mantenimiento) |


### 🗂️ Modelo `[[Marca]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | nombre |


### 🗂️ Modelo `[[Modelo]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | nombre |
| `marca` | `ForeignKey` | `ForeignKey` ➡️ [[Marca]] | marca |
| `categoria` | `ForeignKey` | `ForeignKey` ➡️ [[Categoria]] | categoria |
| `unidad_medida` | `ForeignKey` | `ForeignKey` ➡️ [[UnidadMedida]] | unidad medida (Unidad de medida por defecto) |
| `precio_promedio` | `DecimalField` | - | precio promedio (Precio unitario promedio para presupuestos) |
| `descripcion` | `TextField` | - | descripcion (Descripción detallada del modelo) |
| `imagen_archivo` | `FileField` | - | imagen archivo (Cargar imagen desde el equipo) |
| `imagen_url` | `CharField` | - | imagen url (O pegar una URL externa de la imagen) |
| `materiales_compatibles` | `ManyToManyField` | `ManyToManyField` ➡️ [[Material]] | materiales compatibles |
| `documentos` | `ManyToManyField` | `ManyToManyField` ➡️ [[Documento]] | documentos (Biblioteca de documentos asociados a este modelo) |


### 🗂️ Modelo `[[Activo]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | nombre (Nombre del activo o equipo) |
| `codigo_interno` | `CharField` | - | codigo interno (Código de inventario interno (Solo números)) |
| `epc` | `CharField` | - | epc (Código EPC (Electrónic Product Code) de la etiqueta RFID (Alfanumérico)) |
| `serie` | `CharField` | - | serie (Número de serie del fabricante) |
| `referencia` | `CharField` | - | referencia (Referencia adicional) |
| `marca_legacy` | `CharField` | - | marca legacy |
| `modelo_legacy` | `CharField` | - | modelo legacy |
| `modelo` | `ForeignKey` | `ForeignKey` ➡️ [[Modelo]] | modelo |
| `descripcion` | `TextField` | - | descripcion |
| `fecha_compra` | `DateField` | - | fecha compra |
| `costo` | `DecimalField` | - | costo |
| `estado` | `CharField` | - | estado |
| `responsable` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | responsable (Persona responsable del activo) |
| `familia` | `ForeignKey` | `ForeignKey` ➡️ [[Familia]] | familia (Clasificación por familia de equipo) |
| `padre` | `ForeignKey` | `ForeignKey` ➡️ [[Activo]] | padre (Activo principal del cual este forma parte) |
| `ubicacion_legacy` | `CharField` | - | ubicacion legacy (Ubicación física del activo (Texto libre - Deprecado)) |
| `ubicacion` | `ForeignKey` | `ForeignKey` ➡️ [[Ubicacion]] | ubicacion (Ubicación jerárquica) |
| `plano` | `ForeignKey` | `ForeignKey` ➡️ [[Plano]] | plano (Plano principal donde se ubica este activo) |
| `foto` | `FileField` | - | foto |
| `creado_en` | `DateTimeField` | - | creado en |
| `actualizado_en` | `DateTimeField` | - | actualizado en |


### 🗂️ Modelo `[[VistaGuardada]]`

> **Descripción**: Stores a named set of filters for reuse in the asset super filter.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | nombre |
| `usuario` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | usuario |
| `filtros` | `JSONField` | - | filtros (JSON con los filtros aplicados) |
| `creada_en` | `DateTimeField` | - | creada en |


### 🗂️ Modelo `[[Plano]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | nombre |
| `ubicacion` | `ForeignKey` | `ForeignKey` ➡️ [[Ubicacion]] | ubicacion |
| `documento` | `ForeignKey` | `ForeignKey` ➡️ [[Documento]] | documento (Documento que contiene el archivo del plano (usa la última revisión)) |
| `archivo` | `FileField` | - | archivo (Archivo directo (usar 'documento' para control de versiones)) |
| `tipo_plano` | `CharField` | - | Tipo de Plano |
| `numero_documento` | `CharField` | - | No. de Doc |
| `titulo` | `CharField` | - | Título |
| `disciplina` | `ForeignKey` | `ForeignKey` ➡️ [[Disciplina]] | disciplina (Disciplina y Subdisciplina vinculada al plano) |
| `descripcion` | `TextField` | - | descripcion |
| `creado_en` | `DateTimeField` | - | creado en |
| `activos` | `ManyToManyField` | `ManyToManyField` ➡️ [[Activo]] | activos (Activos que se visualizan en este plano) |


### 🗂️ Modelo `[[VisorPlano]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | nombre |
| `plano` | `ForeignKey` | `ForeignKey` ➡️ [[Plano]] | plano |
| `descripcion` | `TextField` | - | descripcion |
| `creado_en` | `DateTimeField` | - | creado en |


### 🗂️ Modelo `[[PinPlano]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `visor` | `ForeignKey` | `ForeignKey` ➡️ [[VisorPlano]] | visor |
| `activo` | `ForeignKey` | `ForeignKey` ➡️ [[Activo]] | activo |
| `aviso` | `ForeignKey` | `ForeignKey` ➡️ [[Aviso]] | aviso |
| `actividad` | `ForeignKey` | `ForeignKey` ➡️ [[Actividad]] | actividad (Actividad de proyecto ubicada en este punto) |
| `ubicacion` | `ForeignKey` | `ForeignKey` ➡️ [[Ubicacion]] | ubicacion (Ubicación vinculada a esta zona del plano) |
| `x` | `FloatField` | - | x (Posición X (o Left) en píxeles absolutos) |
| `y` | `FloatField` | - | y (Posición Y (o Top) en píxeles absolutos) |
| `ancho` | `FloatField` | - | ancho (Ancho del área en píxeles (0 para puntos)) |
| `alto` | `FloatField` | - | alto (Alto del área en píxeles (0 para puntos)) |
| `color` | `CharField` | - | color |
| `nota` | `TextField` | - | nota |


### 🗂️ Modelo `[[PinFoto]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `pin` | `ForeignKey` | `ForeignKey` ➡️ [[PinPlano]] | pin |
| `imagen` | `FileField` | - | imagen |
| `descripcion` | `CharField` | - | descripcion |
| `creado_en` | `DateTimeField` | - | creado en |


### 🗂️ Modelo `[[PuntoMedicion]]`

> **Descripción**: Representa un punto donde se pueden tomar lecturas para un activo (ej: Horímetro, Termómetro).

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `activo` | `ForeignKey` | `ForeignKey` ➡️ [[Activo]] | activo |
| `nombre` | `CharField` | - | nombre (Ej: Horímetro Motor, Presión Aceite) |
| `codigo` | `CharField` | - | codigo (Código corto opcional) |
| `unidad` | `CharField` | - | unidad (Ej: Hrs, Bar, °C, PSI) |
| `es_acumulativo` | `BooleanField` | - | es acumulativo (Si se marca, el valor se suma al anterior (ej: horímetro)) |
| `valor_objetivo` | `FloatField` | - | valor objetivo (Valor nominal o límite de operación) |
| `tolerancia` | `FloatField` | - | tolerancia (Rango de desviación permitido) |
| `creado_en` | `DateTimeField` | - | creado en |
| `actualizado_en` | `DateTimeField` | - | actualizado en |


### 🗂️ Modelo `[[DocumentoMedicion]]`

> **Descripción**: Representa una lectura individual tomada en un punto de medición.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `punto` | `ForeignKey` | `ForeignKey` ➡️ [[PuntoMedicion]] | punto |
| `activo` | `ForeignKey` | `ForeignKey` ➡️ [[Activo]] | activo |
| `valor` | `FloatField` | - | valor |
| `fecha_lectura` | `DateTimeField` | - | fecha lectura |
| `tecnico` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | tecnico |
| `orden_trabajo` | `ForeignKey` | `ForeignKey` ➡️ [[OrdenTrabajo]] | orden trabajo |
| `observaciones` | `TextField` | - | observaciones |
| `creado_en` | `DateTimeField` | - | creado en |


### 🗂️ Modelo `[[RegistroImportacion]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | nombre (Nombre descriptivo de esta importación) |
| `tipo` | `CharField` | - | tipo (Tipo de datos (Activos, Planos, Submittals, etc.)) |
| `fecha` | `DateTimeField` | - | fecha |
| `usuario` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | usuario |
| `estado` | `CharField` | - | estado |
| `total_filas` | `IntegerField` | - | total filas |
| `filas_nuevas` | `IntegerField` | - | filas nuevas |
| `filas_actualizadas` | `IntegerField` | - | filas actualizadas |
| `filas_omitidas` | `IntegerField` | - | filas omitidas |
| `filas_error` | `IntegerField` | - | filas error |
| `ids_creados` | `TextField` | - | ids creados (IDs de activos creados en esta sesión (JSON)) |
| `resumen_columnas` | `JSONField` | - | resumen columnas (Resumen de qué columnas se actualizaron y cuántas veces) |
| `detalles_error` | `TextField` | - | detalles error |


### 🗂️ Modelo `[[BienAfecto]]`

> **Descripción**: Representa un código patrimonial permanente.
    Puede tener múltiples activos físicos a lo largo del tiempo.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `codigo_interno` | `CharField` | - | codigo interno (Código patrimonial permanente) |
| `nombre` | `CharField` | - | nombre (Descripción del bien afecto) |
| `ubicacion` | `ForeignKey` | `ForeignKey` ➡️ [[Ubicacion]] | ubicacion (Ubicación actual del bien afecto) |
| `plano` | `ForeignKey` | `ForeignKey` ➡️ [[Plano]] | plano (Plano actual del bien afecto (Heredado del activo)) |
| `familia` | `ForeignKey` | `ForeignKey` ➡️ [[Familia]] | familia (Clasificación por familia) |
| `responsable` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | responsable (Persona responsable del bien afecto) |
| `creado_en` | `DateTimeField` | - | creado en |
| `actualizado_en` | `DateTimeField` | - | actualizado en |


### 🗂️ Modelo `[[HistorialBienAfecto]]`

> **Descripción**: Registro de altas y bajas de activos físicos en un bien afecto.
    Permite mantener trazabilidad completa de qué equipos han ocupado un código patrimonial.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `bien_afecto` | `ForeignKey` | `ForeignKey` ➡️ [[BienAfecto]] | bien afecto (Bien afecto al que pertenece este registro) |
| `activo` | `ForeignKey` | `ForeignKey` ➡️ [[Activo]] | activo (Activo físico asignado) |
| `fecha_alta` | `DateTimeField` | - | fecha alta (Fecha de asignación del activo) |
| `usuario_alta` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | usuario alta (Usuario que dio de alta el activo) |
| `fecha_baja` | `DateTimeField` | - | fecha baja (Fecha de baja del activo (vacío = activo actual)) |
| `usuario_baja` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | usuario baja (Usuario que dio de baja el activo) |
| `motivo_baja` | `CharField` | - | motivo baja (Razón de la baja) |
| `observaciones_baja` | `TextField` | - | observaciones baja (Detalles adicionales sobre la baja) |


### 🗂️ Modelo `[[ControlSubmittal]]`

> **Descripción**: Modelo para el control de Fichas y Submittals del proyecto (Matriz de Seguimiento).

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `descripcion` | `TextField` | - | Descripción |
| `especialidad` | `CharField` | - | Especialidad |
| `trab_act_n` | `CharField` | - | TRAB-ACT-N |
| `fecha_recibido` | `DateField` | - | Recibido |
| `codigo_ficha` | `CharField` | - | Código Ficha |
| `codigo_submittal` | `CharField` | - | Código Submittal |
| `num_submittal` | `CharField` | - | No. Submittal |
| `fecha_revisado_epc` | `DateField` | - | Revisado EPC |
| `comentario_epc` | `TextField` | - | Comentario EPC |
| `observacion_epc` | `TextField` | - | Observación de EPC |
| `fecha_envio_sup` | `DateField` | - | Fecha Envío Sup. |
| `transmision_epc_sup` | `CharField` | - | Transmisión EPC / SUP |
| `transmision_sup_epc` | `CharField` | - | Transmisión SUP. / EPC |
| `fecha_recepcion_sup` | `DateField` | - | Fecha Recepción Sup |
| `dictamen_sup` | `CharField` | - | Dictamen SUP |
| `observacion_sup` | `TextField` | - | Observación SUP. |
| `enviado_constructora` | `CharField` | - | Enviado a Constructora |
| `fecha_envio_ccc` | `DateField` | - | Fecha Envío CCC (1) |
| `estatus_aconex` | `CharField` | - | Estatus Aconex |
| `estatus_ccg` | `CharField` | - | Estatus en CCG (ICCE) |
| `carpeta` | `CharField` | - | Carpeta |
| `transmitido_a_ccc` | `CharField` | - | Transmitido a CCC |
| `fecha_envio_ccc_final` | `DateField` | - | Fecha Envío CCC (2) |


### 🗂️ Modelo `[[DocumentoAltaBaja]]`

> **Descripción**: Documento oficial de Alta o Baja de activos.
    Agrupa un listado de activos que se dan de alta o baja.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `tipo` | `CharField` | - | Tipo de Documento |
| `numero` | `CharField` | - | Número de Documento (Se genera automáticamente) |
| `fecha` | `DateField` | - | Fecha del Documento |
| `motivo` | `TextField` | - | Motivo / Justificación |
| `estado` | `CharField` | - | estado |
| `observaciones` | `TextField` | - | Observaciones Adicionales |
| `elaborado_por` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | Elaborado por |
| `autorizado_por` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | Autorizado por |
| `recibido_por` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | Recibido por |
| `creado_en` | `DateTimeField` | - | creado en |
| `actualizado_en` | `DateTimeField` | - | actualizado en |


### 🗂️ Modelo `[[ItemAltaBaja]]`

> **Descripción**: Ítem individual dentro de un documento de Alta/Baja.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `documento` | `ForeignKey` | `ForeignKey` ➡️ [[DocumentoAltaBaja]] | documento |
| `activo` | `ForeignKey` | `ForeignKey` ➡️ [[Activo]] | activo |
| `observacion` | `CharField` | - | observacion (Observación específica para este activo) |


### 🗂️ Modelo `[[ArchivoAltaBaja]]`

> **Descripción**: Archivo adjunto a un Documento de Alta/Baja.
    Puede ser imagen, PDF, o cualquier tipo de archivo.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `documento` | `ForeignKey` | `ForeignKey` ➡️ [[DocumentoAltaBaja]] | documento |
| `archivo` | `FileField` | - | Archivo |
| `comentario` | `CharField` | - | Comentario |
| `subido_en` | `DateTimeField` | - | subido en |


### 🗂️ Modelo `[[PlantillaEtiquetaQR]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | Nombre del Molde |
| `ancho_cm` | `DecimalField` | - | Ancho (cm) |
| `alto_cm` | `DecimalField` | - | Alto (cm) |
| `prefijo_defecto` | `CharField` | - | Prefijo Frecuente |
| `padding_digitos` | `IntegerField` | - | Dígitos de Padding |
| `header_text` | `CharField` | - | Texto Cabecera |
| `footer_mode` | `CharField` | - | Modo de Pie |
| `font_size` | `IntegerField` | - | Tamaño Fuente (pt) |
| `qr_scale` | `IntegerField` | - | Escala QR (%) |
| `border_thickness` | `IntegerField` | - | Grosor Borde (px) |
| `margin_top` | `DecimalField` | - | Margen Superior (cm) |
| `compiled_html` | `TextField` | - | HTML Compilado Interno |
| `activo` | `BooleanField` | - | Activo |
| `creado_en` | `DateTimeField` | - | creado en |
| `modificado_en` | `DateTimeField` | - | modificado en |


### 🗂️ Modelo `[[FotoUbicacion]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `ubicacion` | `ForeignKey` | `ForeignKey` ➡️ [[Ubicacion]] | ubicacion |
| `foto` | `FileField` | - | foto |
| `descripcion` | `CharField` | - | Descripción |
| `subido_por` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | subido por |
| `creado_en` | `DateTimeField` | - | creado en |


### 🗂️ Modelo `[[ReporteGenerado]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `UUIDField` | - | id |
| `usuario` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | usuario |
| `nombre` | `CharField` | - | nombre (Nombre descriptivo del reporte) |
| `estado` | `CharField` | - | estado |
| `task_id` | `CharField` | - | task id (ID de la tarea en Celery) |
| `archivo` | `FileField` | - | archivo |
| `detalles_error` | `TextField` | - | detalles error |
| `creado_en` | `DateTimeField` | - | creado en |
| `completado_en` | `DateTimeField` | - | completado en |


### 🗂️ Modelo `[[DowntimeActivo]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `activo` | `ForeignKey` | `ForeignKey` ➡️ [[Activo]] | activo |
| `orden_trabajo` | `ForeignKey` | `ForeignKey` ➡️ [[OrdenTrabajo]] | orden trabajo |
| `aviso` | `ForeignKey` | `ForeignKey` ➡️ [[Aviso]] | aviso |
| `inicio` | `DateTimeField` | - | inicio |
| `fin` | `DateTimeField` | - | fin |
| `duracion_horas` | `FloatField` | - | duracion horas (Duración calculada en horas) |
| `motivo` | `CharField` | - | motivo |
| `hallazgos` | `TextField` | - | hallazgos |
| `creado_en` | `DateTimeField` | - | creado en |
| `actualizado_en` | `DateTimeField` | - | actualizado en |


### 🗂️ Modelo `[[CaracteristicaCategoria]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `categoria` | `ForeignKey` | `ForeignKey` ➡️ [[Categoria]] | categoria |
| `nombre` | `CharField` | - | nombre (Ej: Capacidad, Voltaje, Color) |
| `tipo_dato` | `CharField` | - | tipo dato |
| `unidad_medida` | `ForeignKey` | `ForeignKey` ➡️ [[UnidadMedida]] | unidad medida |
| `opciones` | `CharField` | - | opciones (Opciones separadas por coma si eligió 'Lista de Opciones'. Ej: Rojo,Verde,Azul) |
| `requerido` | `BooleanField` | - | requerido |


### 🗂️ Modelo `[[ValorCaracteristicaModelo]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `modelo` | `ForeignKey` | `ForeignKey` ➡️ [[Modelo]] | modelo |
| `caracteristica` | `ForeignKey` | `ForeignKey` ➡️ [[CaracteristicaCategoria]] | caracteristica |
| `valor` | `CharField` | - | valor |



---
🔙 Volver a [[00_Inicio|Inicio]]