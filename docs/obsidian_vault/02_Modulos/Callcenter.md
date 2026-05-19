# 📂 Módulo: Call Center y Tickets de Soporte (`callcenter`)

> [!INFO]
> **Etiquetas**: #django/app #callcenter 
> **Propósito**: MAO
> **Ubicación en Código**: `file:///d:/Apps/energia/energy/callcenter`

---

## 📦 Modelos de Datos (Base de Datos)

Este módulo gestiona los siguientes modelos en la base de datos. Los campos ForeignKey y relaciones ManyToMany se representan con enlaces `[[ModelName]]` para navegar interactivamente en Obsidian.

### 🗂️ Modelo `[[SolicitudTicket]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `id_solicitud` | `BigIntegerField` | - | ID Solicitud Servicio |
| `folio` | `CharField` | - | Folio |
| `es_interno` | `BooleanField` | - | Es Ticket Interno |
| `solicitante` | `CharField` | - | solicitante |
| `responsable` | `CharField` | - | Responsable de Atención |
| `solicitud_descripcion` | `TextField` | - | Descripción Solicitud |
| `falla_descripcion` | `TextField` | - | Descripción Falla |
| `falla_clasificacion` | `CharField` | - | Clasificación Falla |
| `servicio` | `CharField` | - | servicio |
| `subservicio` | `CharField` | - | subservicio |
| `unidad` | `CharField` | - | unidad |
| `area` | `CharField` | - | area |
| `grupo` | `CharField` | - | grupo |
| `nivel` | `CharField` | - | nivel |
| `fecha_solicitud` | `DateTimeField` | - | Fecha Solicitud |
| `tipo_recepcion` | `CharField` | - | Tipo Recepción |
| `fecha_tipo_recepcion` | `DateTimeField` | - | Fecha Tipo Recepción |
| `fecha_suspension` | `DateTimeField` | - | Fecha Suspensión |
| `fecha_cierre` | `DateTimeField` | - | Fecha Cierre |
| `tipo_solicitud` | `CharField` | - | Tipo Solicitud |
| `tiempo_tipo` | `CharField` | - | Tiempo Tipo |
| `fecha_diagnostico` | `DateTimeField` | - | Fecha/Hora Diagnóstico |
| `diagnostico` | `TextField` | - | Diagnóstico |
| `fecha_actividades` | `DateTimeField` | - | Fecha/Hora Actividades |
| `actividades` | `TextField` | - | Actividades |
| `fecha_observaciones` | `DateTimeField` | - | Fecha/Hora Observaciones |
| `observaciones` | `TextField` | - | Observaciones |
| `fecha_observaciones_usuario` | `DateTimeField` | - | Fecha/Hora Obs. Usuario |
| `observaciones_usuario` | `TextField` | - | Observaciones Usuario |
| `clasificacion_falla_final` | `CharField` | - | Clasificación Falla Final |
| `categoria_falla` | `CharField` | - | Categoría Falla |
| `embedding` | `VectorField` | - | embedding |
| `falla_reportada` | `ForeignKey` | `ForeignKey` ➡️ [[FallaTicket]] | Falla del Catálogo |
| `cierre_enviado` | `BooleanField` | - | Cierre Notificado |
| `correo_cierre` | `BooleanField` | - | Correo de Cierre Enviado (Se marca automáticamente cuando Power Automate confirma el envío del correo de cierre) |
| `activo` | `ForeignKey` | `ForeignKey` ➡️ [[Activo]] | Activo Relacionado |
| `ubicacion` | `ForeignKey` | `ForeignKey` ➡️ [[Ubicacion]] | Ubicación Física |
| `usuario_responsable` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | Usuario Responsable |
| `creado_en` | `DateTimeField` | - | creado en |
| `actualizado_en` | `DateTimeField` | - | actualizado en |
| `deductiva` | `DecimalField` | - | Deductiva (USD) (Monto de la deductiva en USD) |
| `proveedor_deductiva` | `ForeignKey` | `ForeignKey` ➡️ [[Empresa]] | Proveedor de Deductiva |


### 🗂️ Modelo `[[GrupoTicket]]`

> **Descripción**: Agrupa múltiples tickets de Call Center bajo un mismo correlativo y descripción.
    Relación muchos a muchos.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `correlativo` | `CharField` | - | Número de Grupo / Cluster |
| `fecha` | `DateTimeField` | - | Fecha de Creación |
| `departamento` | `ForeignKey` | `ForeignKey` ➡️ [[Departamento]] | Departamento Responsable |
| `usuario_creador` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | Creado por |
| `descripcion` | `TextField` | - | Descripción del Grupo |
| `tickets` | `ManyToManyField` | `ManyToManyField` ➡️ [[SolicitudTicket]] | Tickets |


### 🗂️ Modelo `[[EvidenciaTicket]]`

> **Descripción**: Repositorio de imágenes, fotos o documentos adjuntos para un ticket específico.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `ticket` | `ForeignKey` | `ForeignKey` ➡️ [[SolicitudTicket]] | Ticket |
| `archivo` | `FileField` | - | Archivo/Foto |
| `descripcion` | `CharField` | - | Descripción Corta |
| `descripcion_ia` | `TextField` | - | Análisis de IA (Visual) |
| `analizada` | `BooleanField` | - | Analizada por IA |
| `fecha_carga` | `DateTimeField` | - | fecha carga |


### 🗂️ Modelo `[[Institucion]]`

> **Descripción**: Representa una institución externa (ej. SAR, BANX, etc.)
    que solicita extensiones de tiempo o soluciones provisionales.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | Nombre de la Institución |
| `acronimo` | `CharField` | - | Acrónimo (Ej: SAR, BANX, etc.) |
| `ubicaciones` | `ManyToManyField` | `ManyToManyField` ➡️ [[Ubicacion]] | Ubicaciones de la Institución (Una institución puede tener una o más ubicaciones físicas.) |


### 🗂️ Modelo `[[Enlace]]`

> **Descripción**: Persona de contacto en una institución para el seguimiento de tickets.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | Nombre Completo |
| `email` | `CharField` | - | Correo Electrónico |
| `telefono` | `CharField` | - | Teléfono / WhatsApp |
| `institucion` | `ForeignKey` | `ForeignKey` ➡️ [[Institucion]] | Institución |
| `ubicacion` | `ForeignKey` | `ForeignKey` ➡️ [[Ubicacion]] | Ubicación por Defecto |


### 🗂️ Modelo `[[TiempoAcordado]]`

> **Descripción**: Acuerdo de extensión de tiempo superando la holgura permitida.
    Incluye cronograma de tareas para vista Gantt/Timeline.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `ticket` | `ForeignKey` | `ForeignKey` ➡️ [[SolicitudTicket]] | Ticket Relacionado |
| `enlace` | `ForeignKey` | `ForeignKey` ➡️ [[Enlace]] | Enlace Solicitante |
| `ubicacion` | `ForeignKey` | `ForeignKey` ➡️ [[Ubicacion]] | Ubicación del Reporte |
| `institucion` | `ForeignKey` | `ForeignKey` ➡️ [[Institucion]] | Institución |
| `motivo_extension` | `TextField` | - | Motivo del Tiempo Acordado |
| `solucion_provisional` | `TextField` | - | Solución Provisional Acordada |
| `observaciones` | `TextField` | - | Observaciones Adicionales |
| `fecha_solucion_final` | `DateTimeField` | - | Fecha Solución Final Comprometida |
| `estatus` | `CharField` | - | Estado del Acuerdo |
| `enviado` | `BooleanField` | - | ¿Enviado por Correo? (Indica si el reporte PDF ya fue enviado a través del flujo de Power Automate.) |
| `firma_enlace` | `TextField` | - | Firma del Enlace |
| `firma_responsable` | `TextField` | - | Firma del Responsable |
| `usuario_creador` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | usuario creador |
| `departamento` | `ForeignKey` | `ForeignKey` ➡️ [[Departamento]] | departamento |
| `creado_en` | `DateTimeField` | - | creado en |
| `actualizado_en` | `DateTimeField` | - | actualizado en |


### 🗂️ Modelo `[[TiempoAcordadoTarea]]`

> **Descripción**: Tareas específicas dentro de un tiempo acordado para generar el cronograma.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `tiempo_acordado` | `ForeignKey` | `ForeignKey` ➡️ [[TiempoAcordado]] | Acuerdo |
| `descripcion` | `CharField` | - | Actividad / Tarea |
| `fecha_inicio` | `DateTimeField` | - | Fecha de Inicio |
| `fecha_fin` | `DateTimeField` | - | Fecha Final |
| `completada` | `BooleanField` | - | ¿Completada? |


### 🗂️ Modelo `[[RestriccionAcceso]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `ticket` | `OneToOneField` | `OneToOneField` ➡️ [[SolicitudTicket]] | Ticket Relacionado |
| `folio_ra` | `CharField` | - | Folio RA |
| `fecha_restriccion` | `DateTimeField` | - | Fecha y Hora de Restricción |
| `fecha_reprogramacion` | `DateTimeField` | - | Fecha y Hora de Reprogramación |
| `horas_restriccion` | `DecimalField` | - | Horas de Restricción |
| `firma_usuario` | `TextField` | - | Firma del Usuario |
| `firma_tecnico` | `TextField` | - | Firma del Técnico |
| `usuario_creador` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | usuario creador |
| `creado_en` | `DateTimeField` | - | creado en |


### 🗂️ Modelo `[[CronogramaPredefinido]]`

> **Descripción**: Plantilla de cronograma para reutilizar en acuerdos de tiempo.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | Nombre del Cronograma |
| `departamento` | `ForeignKey` | `ForeignKey` ➡️ [[Departamento]] | Departamento / Área |


### 🗂️ Modelo `[[CronogramaItemPredefinido]]`

> **Descripción**: Actividad individual dentro de una plantilla de cronograma.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `cronograma` | `ForeignKey` | `ForeignKey` ➡️ [[CronogramaPredefinido]] | Cronograma |
| `numero` | `PositiveIntegerField` | - | N° |
| `descripcion` | `CharField` | - | Descripción de la Tarea |
| `duracion_dias` | `PositiveIntegerField` | - | Duración (Días) |
| `predecesores` | `ManyToManyField` | `ManyToManyField` ➡️ [[CronogramaItemPredefinido]] | Predecesores |


### 🗂️ Modelo `[[FallaTicket]]`

> **Descripción**: Catálogo de fallas estandarizadas para el Call Center.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | Nombre de la Falla |
| `parent` | `ForeignKey` | `ForeignKey` ➡️ [[FallaTicket]] | Falla Padre |
| `descripcion` | `TextField` | - | Descripción Adicional |
| `departamento_responsable` | `ForeignKey` | `ForeignKey` ➡️ [[Departamento]] | Departamento Responsable |
| `usuario_responsable` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | Responsable por Defecto |



---
🔙 Volver a [[00_Inicio|Inicio]]