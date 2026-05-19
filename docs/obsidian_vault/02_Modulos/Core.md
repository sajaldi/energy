# 📂 Módulo: Núcleo del Sistema (Core) (`core`)

> [!INFO]
> **Etiquetas**: #django/app #core 
> **Propósito**: Provisión y Gestión
> **Ubicación en Código**: `file:///d:/Apps/energia/energy/core`

---

## 📦 Modelos de Datos (Base de Datos)

Este módulo gestiona los siguientes modelos en la base de datos. Los campos ForeignKey y relaciones ManyToMany se representan con enlaces `[[ModelName]]` para navegar interactivamente en Obsidian.

### 🗂️ Modelo `[[ConfiguracionUI]]`

> **Descripción**: Singleton model for storing global UI color settings.
    Includes colors for the Maintenance Matrix.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `titulo_proyecto` | `CharField` | - | titulo proyecto (Título en la barra superior) |
| `color_primario` | `CharField` | - | Color Primario (Botones, Headers) |
| `color_secundario` | `CharField` | - | Color Secundario |
| `matriz_header_bg` | `CharField` | - | Fondo Encabezado Matriz |
| `matriz_header_text` | `CharField` | - | Texto Encabezado Matriz |
| `matriz_border_color` | `CharField` | - | Color de Bordes Matriz |
| `matriz_hover_row` | `CharField` | - | Hover Fila |
| `matriz_hover_cell` | `CharField` | - | Hover Celda |
| `orden_preventiva_bg` | `CharField` | - | Fondo OT Preventiva |
| `orden_correctiva_bg` | `CharField` | - | Fondo OT Correctiva |
| `orden_texto` | `CharField` | - | Texto OT |


### 🗂️ Modelo `[[TipoMedidor]]`

> **Descripción**: Representa un tipo de medidor.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | nombre |
| `descripcion` | `TextField` | - | descripcion |


### 🗂️ Modelo `[[UnidadMedida]]`

> **Descripción**: Representa una unidad de medida.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | nombre |
| `simbolo` | `CharField` | - | simbolo |
| `descripcion` | `TextField` | - | descripcion |


### 🗂️ Modelo `[[Medidor]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | nombre |
| `tipo` | `CharField` | - | tipo |
| `tipo_medidor` | `ForeignKey` | `ForeignKey` ➡️ [[TipoMedidor]] | tipo medidor |
| `medidor_padre` | `ForeignKey` | `ForeignKey` ➡️ [[Medidor]] | medidor padre |
| `unidad` | `ForeignKey` | `ForeignKey` ➡️ [[UnidadMedida]] | unidad |


### 🗂️ Modelo `[[VistaConsumoDiferencia]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `medidor_id` | `IntegerField` | - | medidor id |
| `fecha` | `DateTimeField` | - | fecha |
| `consumo` | `FloatField` | - | consumo |
| `consumo_anterior` | `FloatField` | - | consumo anterior |
| `diferencia_consumo` | `FloatField` | - | diferencia consumo |


### 🗂️ Modelo `[[Consumo]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `fecha` | `DateTimeField` | - | fecha |
| `consumo` | `FloatField` | - | consumo |
| `medidor` | `ForeignKey` | `ForeignKey` ➡️ [[Medidor]] | medidor |


### 🗂️ Modelo `[[InterfaceConsumo]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `fecha` | `DateTimeField` | - | fecha |
| `consumo` | `FloatField` | - | consumo |
| `medidor` | `CharField` | - | medidor |


### 🗂️ Modelo `[[Equipo]]`

> **Descripción**: Representa un equipo en el sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `numero_equipo` | `CharField` | - | numero equipo |
| `descripcion` | `CharField` | - | descripcion |


### 🗂️ Modelo `[[UbicacionTecnica]]`

> **Descripción**: Representa una ubicación técnica en el sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `codigo_ubicacion` | `CharField` | - | codigo ubicacion |
| `descripcion` | `CharField` | - | descripcion |


### 🗂️ Modelo `[[CategoriaPuntoMedicion]]`

> **Descripción**: Clasifica los puntos de medición por su tipo.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | nombre |
| `descripcion` | `TextField` | - | descripcion |


### 🗂️ Modelo `[[CaracteristicaMedicion]]`

> **Descripción**: Define la característica que se mide (ej. Temperatura, Presión) y su unidad.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | nombre |
| `unidad_medida` | `CharField` | - | unidad medida |
| `descripcion` | `TextField` | - | descripcion |


### 🗂️ Modelo `[[RangoMedicion]]`

> **Descripción**: Define rangos personalizados para cada característica de medición.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `caracteristica` | `ForeignKey` | `ForeignKey` ➡️ [[CaracteristicaMedicion]] | caracteristica |
| `valor_min` | `FloatField` | - | Valor mínimo |
| `valor_max` | `FloatField` | - | Valor máximo |
| `descripcion` | `CharField` | - | Descripción |
| `color` | `CharField` | - | Color representativo |


### 🗂️ Modelo `[[PuntoMedicion]]`

> **Descripción**: Representa un punto específico donde se realiza una medición.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `numero_interno` | `AutoField` | - | numero interno |
| `descripcion` | `CharField` | - | descripcion |
| `objeto_tecnico_equipo` | `ForeignKey` | `ForeignKey` ➡️ [[Equipo]] | Equipo Asociado |
| `objeto_tecnico_ubicacion` | `ForeignKey` | `ForeignKey` ➡️ [[UbicacionTecnica]] | Ubicación Técnica Asociada |
| `categoria` | `ForeignKey` | `ForeignKey` ➡️ [[CategoriaPuntoMedicion]] | categoria |
| `caracteristica` | `ForeignKey` | `ForeignKey` ➡️ [[CaracteristicaMedicion]] | caracteristica |
| `es_contador` | `BooleanField` | - | Es Contador |


### 🗂️ Modelo `[[DocumentoMedicion]]`

> **Descripción**: Registra las lecturas tomadas en los puntos de medición.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `punto_medicion` | `ForeignKey` | `ForeignKey` ➡️ [[PuntoMedicion]] | punto medicion |
| `fecha_hora_lectura` | `DateTimeField` | - | Fecha y hora de lectura |
| `valor_leido` | `FloatField` | - | valor leido |
| `lectura_contador` | `FloatField` | - | Lectura de Contador (si aplica) |
| `observaciones` | `TextField` | - | observaciones |


### 🗂️ Modelo `[[Servicio]]`

> **Descripción**: Representa un servicio para agrupar KPIs.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | nombre |
| `descripcion` | `TextField` | - | descripcion |


### 🗂️ Modelo `[[KPI]]`

> **Descripción**: Representa un indicador clave de rendimiento (KPI).

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `kpi` | `CharField` | - | KPI |
| `descripcion` | `TextField` | - | Descripción |
| `servicio` | `ForeignKey` | `ForeignKey` ➡️ [[Servicio]] | Servicio |


### 🗂️ Modelo `[[Departamento]]`

> **Descripción**: Representa un departamento de la empresa.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | Nombre del Departamento |
| `descripcion` | `TextField` | - | Descripción |
| `responsable` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | Responsable / Jefe de departamento |


### 🗂️ Modelo `[[PerfilUsuario]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `usuario` | `OneToOneField` | `OneToOneField` ➡️ [[User]] | usuario |
| `visto_tutorial` | `BooleanField` | - | Visto tutorial |
| `telefono` | `CharField` | - | Teléfono |
| `departamento` | `ForeignKey` | `ForeignKey` ➡️ [[Departamento]] | Departamento |
| `ubicacion_defecto` | `ForeignKey` | `ForeignKey` ➡️ [[Ubicacion]] | Ubicación por Defecto |
| `responsable` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | Responsable / Jefe Directo |


### 🗂️ Modelo `[[VistaPersonalizada]]`

> **Descripción**: Permite guardar filtros del admin como vistas personalizadas.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `usuario` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | usuario |
| `nombre` | `CharField` | - | nombre |
| `app_label` | `CharField` | - | app label |
| `model_name` | `CharField` | - | model name |
| `query_string` | `TextField` | - | query string (Query string del filtro (ej: ?empresa__id=1)) |
| `es_publica` | `BooleanField` | - | ¿Es pública? |
| `color` | `CharField` | - | Color de la etiqueta |
| `icono` | `CharField` | - | Icono FontAwesome |
| `creado_en` | `DateTimeField` | - | creado en |


### 🗂️ Modelo `[[KnowledgeChunk]]`

> **Descripción**: Fragmento de conocimiento para búsqueda vectorial.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `content` | `TextField` | - | content |
| `embedding` | `VectorField` | - | embedding |
| `source` | `CharField` | - | source |
| `metadata` | `JSONField` | - | metadata |
| `created_at` | `DateTimeField` | - | created at |


### 🗂️ Modelo `[[ElementoApp]]`

> **Descripción**: Configura la visibilidad de cada sección/botón del dashboard móvil
    según los Grupos de Django. Si no tiene grupos asignados, es visible para todos.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `clave` | `CharField` | - | clave (Identificador interno (ej: auditoria, finanzas, logistica)) |
| `nombre` | `CharField` | - | nombre (Nombre visible en el admin (ej: Auditoría, Gestión Financiera)) |
| `descripcion` | `CharField` | - | descripcion |
| `activo` | `BooleanField` | - | activo (Desactivar para ocultar globalmente) |
| `orden` | `PositiveIntegerField` | - | orden (Orden de aparición) |
| `grupos` | `ManyToManyField` | `ManyToManyField` ➡️ [[Group]] | grupos (Grupos que pueden ver este elemento. Si está vacío, es visible para TODOS.) |



---
🔙 Volver a [[00_Inicio|Inicio]]