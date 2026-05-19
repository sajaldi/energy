# 📂 Módulo: Gestión de Mantenimiento (CMMS) (`mantenimiento`)

> [!INFO]
> **Etiquetas**: #django/app #mantenimiento 
> **Propósito**: Mantenimiento
> **Ubicación en Código**: `file:///d:/Apps/energia/energy/mantenimiento`

---

## 📦 Modelos de Datos (Base de Datos)

Este módulo gestiona los siguientes modelos en la base de datos. Los campos ForeignKey y relaciones ManyToMany se representan con enlaces `[[ModelName]]` para navegar interactivamente en Obsidian.

### 🗂️ Modelo `[[Tipo]]`

> **Descripción**: Tipo jerárquico para clasificar rutinas de mantenimiento.
    Reemplaza el sistema anterior de Categoría/Disciplina/SubDisciplina.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | nombre |
| `codigo` | `CharField` | - | Código |
| `padre` | `ForeignKey` | `ForeignKey` ➡️ [[Tipo]] | padre |
| `categoria_activo` | `ForeignKey` | `ForeignKey` ➡️ [[Categoria]] | categoria activo (Vincular con una categoría de activo particular) |
| `servicio` | `ForeignKey` | `ForeignKey` ➡️ [[Servicio]] | servicio (Servicio al que pertenece esta categoría (se hereda a rutinas e hijos)) |
| `descripcion` | `TextField` | - | descripcion |


### 🗂️ Modelo `[[Frecuencia]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | nombre (Ej: Diario, Semanal, Mensual) |
| `dias` | `PositiveIntegerField` | - | dias (Cantidad de días para el intervalo) |


### 🗂️ Modelo `[[PuestoTrabajo]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | nombre |
| `descripcion` | `TextField` | - | descripcion |


### 🗂️ Modelo `[[Empresa]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | nombre |
| `descripcion` | `TextField` | - | descripcion |
| `activo` | `BooleanField` | - | activo |
| `creado_en` | `DateTimeField` | - | creado en |
| `actualizado_en` | `DateTimeField` | - | actualizado en |
| `dynamics_guid` | `UUIDField` | - | GUID de Dynamics |


### 🗂️ Modelo `[[DocumentoEmpresa]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `empresa` | `ForeignKey` | `ForeignKey` ➡️ [[Empresa]] | empresa |
| `tipo_documento` | `CharField` | - | tipo documento |
| `mes` | `PositiveIntegerField` | - | mes (Mes de aplicación (1-12). Dejar vacío si es DOC ÚNICO.) |
| `anio` | `PositiveIntegerField` | - | anio (Año de aplicación (ej. 2026)) |
| `archivo` | `FileField` | - | archivo (Archivo físico a subir a MinIO) |
| `descripcion` | `CharField` | - | descripcion (Aclaración adicional) |
| `es_valido` | `BooleanField` | - | es valido (Si no es válido, no contará para la autorización de QR.) |
| `creado_en` | `DateTimeField` | - | creado en |
| `actualizado_en` | `DateTimeField` | - | actualizado en |


### 🗂️ Modelo `[[TecnicoPuesto]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `user` | `OneToOneField` | `OneToOneField` ➡️ [[User]] | user |
| `nombre` | `CharField` | - | Nombre(s) |
| `apellido` | `CharField` | - | Apellido(s) |
| `puesto` | `ForeignKey` | `ForeignKey` ➡️ [[PuestoTrabajo]] | puesto |
| `empresa` | `ForeignKey` | `ForeignKey` ➡️ [[Empresa]] | empresa |
| `dni` | `CharField` | - | dni (Ej: 0501-1986-06985) |
| `fecha_nacimiento` | `DateField` | - | fecha nacimiento |
| `tipo_sangre` | `CharField` | - | tipo sangre |
| `fecha_alta` | `DateField` | - | fecha alta (Fecha de ingreso a la empresa) |
| `disponible` | `BooleanField` | - | disponible |
| `esta_vigente` | `BooleanField` | - | Vigente (Si no está vigente, no podrá ingresar al recinto) |
| `codigo_asistencia` | `CharField` | - | Código QR Carnet (ID del carnet físico (ej. PERSONAL0001)) |
| `foto` | `FileField` | - | Foto de Perfil |
| `horas_semanales_max` | `DecimalField` | - | horas semanales max (Capacidad máxima de horas por semana) |


### 🗂️ Modelo `[[Asistencia]]`

> **Descripción**: Registro diario de ingresos y egresos de técnicos mediante escaneo de QR.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `tecnico` | `ForeignKey` | `ForeignKey` ➡️ [[TecnicoPuesto]] | Técnico |
| `fecha` | `DateField` | - | fecha |
| `hora_entrada` | `TimeField` | - | Hora de Entrada |
| `hora_salida` | `TimeField` | - | Hora de Salida |
| `empresa_registro` | `ForeignKey` | `ForeignKey` ➡️ [[Empresa]] | Empresa en Registro |
| `usuario_estacion` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | Operador Estación |
| `creado_en` | `DateTimeField` | - | creado en |
| `actualizado_en` | `DateTimeField` | - | actualizado en |


### 🗂️ Modelo `[[PasoRutina]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `rutina` | `ForeignKey` | `ForeignKey` ➡️ [[Rutina]] | rutina |
| `orden` | `PositiveIntegerField` | - | orden |
| `descripcion` | `TextField` | - | descripcion (Descripción de la tarea a realizar) |
| `tipo_respuesta` | `CharField` | - | tipo respuesta |
| `verificacion` | `CharField` | - | verificacion (¿Qué debe verificar el técnico?) |
| `unidad_medida` | `CharField` | - | unidad medida (Ej: Bar, °C, Amperios) |
| `valor_objetivo` | `FloatField` | - | valor objetivo (Valor ideal esperado) |
| `rango_min` | `FloatField` | - | rango min |
| `rango_max` | `FloatField` | - | rango max |
| `punto_medicion_exacto` | `ForeignKey` | `ForeignKey` ➡️ [[PuntoMedicion]] | punto medicion exacto (Vincular a un punto específico (procedimientos detallados)) |
| `punto_medicion_codigo` | `CharField` | - | punto medicion codigo (Vincular por código (ej: 'NIVEL_ACEITE') para procedimientos genéricos) |


### 🗂️ Modelo `[[MediaPasoRutina]]`

> **Descripción**: Archivos multimedia (fotos/videos) de referencia para un paso de rutina.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `paso` | `ForeignKey` | `ForeignKey` ➡️ [[PasoRutina]] | paso |
| `archivo` | `FileField` | - | archivo (Foto o video de referencia) |
| `tipo` | `CharField` | - | tipo |
| `descripcion` | `CharField` | - | descripcion (Descripción breve del archivo) |
| `orden` | `PositiveIntegerField` | - | orden |
| `creado_en` | `DateTimeField` | - | creado en |


### 🗂️ Modelo `[[Rutina]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `codigo_rutina` | `CharField` | - | codigo rutina (Código identificador de la rutina) |
| `nombre` | `CharField` | - | nombre (Deje vacío para generar un nombre automático basado en frecuencia y tipo) |
| `ubicacion_predeterminada` | `ForeignKey` | `ForeignKey` ➡️ [[Ubicacion]] | ubicacion predeterminada (Ubicación física predeterminada donde se suele realizar esta rutina) |
| `categoria_activo` | `ForeignKey` | `ForeignKey` ➡️ [[Categoria]] | categoria activo (Categoría de activo a la que aplica esta rutina) |
| `horario_predeterminado` | `ForeignKey` | `ForeignKey` ➡️ [[Horario]] | horario predeterminado (Horario predeterminado sugerido para la ejecución de esta rutina) |
| `tipo` | `ForeignKey` | `ForeignKey` ➡️ [[Tipo]] | tipo (Clasificación de mantenimiento (ej: Mecánica, Eléctrica)) |
| `descripcion` | `TextField` | - | descripcion |
| `frecuencia` | `ForeignKey` | `ForeignKey` ➡️ [[Frecuencia]] | frecuencia |
| `puesto_trabajo` | `ForeignKey` | `ForeignKey` ➡️ [[PuestoTrabajo]] | puesto trabajo (Puesto de trabajo responsable de esta rutina) |
| `tiempo_estimado` | `DurationField` | - | tiempo estimado (Tiempo estimado para completar la rutina (ej: 02:00:00)) |
| `cantidad_tecnicos` | `IntegerField` | - | cantidad tecnicos (Número de técnicos requeridos) |
| `herramientas` | `TextField` | - | herramientas (Herramientas y materiales necesarios) |
| `es_invasiva` | `BooleanField` | - | es invasiva (¿Requiere apagar equipos o realizarse en horarios no operativos?) |
| `creado_en` | `DateTimeField` | - | creado en |
| `actualizado_en` | `DateTimeField` | - | actualizado en |


### 🗂️ Modelo `[[Horario]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | nombre |
| `color` | `CharField` | - | color (Color para identificar este horario en el cronograma) |
| `descripcion` | `TextField` | - | descripcion |


### 🗂️ Modelo `[[DiaHorario]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `horario` | `ForeignKey` | `ForeignKey` ➡️ [[Horario]] | horario |
| `dia` | `IntegerField` | - | dia |
| `hora_inicio` | `TimeField` | - | hora inicio |
| `hora_fin` | `TimeField` | - | hora fin |


### 🗂️ Modelo `[[RestriccionCalendario]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `fecha` | `DateField` | - | fecha (Fecha no laborable o restringida) |
| `motivo` | `CharField` | - | motivo (Razón de la restricción (ej. Feriado, Vacaciones)) |


### 🗂️ Modelo `[[PlanificacionMensual]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `mes` | `PositiveIntegerField` | - | mes |
| `anio` | `PositiveIntegerField` | - | anio |
| `nombre` | `CharField` | - | nombre (Ej: Mantenimiento Preventivo Enero 2024) |
| `estado` | `CharField` | - | estado |
| `responsable` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | responsable |
| `notas` | `TextField` | - | notas |
| `creado_en` | `DateTimeField` | - | creado en |
| `actualizado_en` | `DateTimeField` | - | actualizado en |


### 🗂️ Modelo `[[Programacion]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `rutina` | `ForeignKey` | `ForeignKey` ➡️ [[Rutina]] | rutina |
| `fecha_inicio` | `DateField` | - | fecha inicio (Fecha de inicio para la generación de órdenes) |
| `fecha_fin` | `DateField` | - | fecha fin (Opcional: Fecha límite (un año por defecto si está vacío)) |
| `procesada` | `BooleanField` | - | procesada (Indica si ya se han generado las órdenes para esta programación) |
| `creado_en` | `DateTimeField` | - | creado en |
| `actualizado_en` | `DateTimeField` | - | actualizado en |
| `horarios` | `ManyToManyField` | `ManyToManyField` ➡️ [[Horario]] | horarios (Seleccione uno o más horarios para la programación) |
| `areas` | `ManyToManyField` | `ManyToManyField` ➡️ [[Ubicacion]] | areas (Seleccione las áreas para filtrar los activos) |
| `activos` | `ManyToManyField` | `ManyToManyField` ➡️ [[Activo]] | activos (Seleccione los activos específicos a programar) |


### 🗂️ Modelo `[[Falla]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | nombre |
| `descripcion` | `TextField` | - | descripcion |
| `padre` | `ForeignKey` | `ForeignKey` ➡️ [[Falla]] | padre (Dejar en blanco si es nivel superior) |
| `tipo_aviso` | `CharField` | - | tipo aviso (Filtrar por este tipo de aviso en la App móvil) |
| `puestos_trabajo` | `ManyToManyField` | `ManyToManyField` ➡️ [[PuestoTrabajo]] | puestos trabajo (Vincular a puestos si es el nodo raíz) |


### 🗂️ Modelo `[[Aviso]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `activo` | `ForeignKey` | `ForeignKey` ➡️ [[Activo]] | activo |
| `proyecto` | `ForeignKey` | `ForeignKey` ➡️ [[Proyecto]] | Proyecto |
| `ubicacion` | `ForeignKey` | `ForeignKey` ➡️ [[Ubicacion]] | ubicacion |
| `falla` | `ForeignKey` | `ForeignKey` ➡️ [[Falla]] | falla |
| `descripcion` | `TextField` | - | descripcion (Descripción detallada de la falla o solicitud) |
| `prioridad` | `CharField` | - | prioridad |
| `tipo` | `CharField` | - | tipo |
| `estado` | `CharField` | - | estado |
| `solicitante` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | solicitante |
| `responsable` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | Responsable Asignado |
| `departamento` | `ForeignKey` | `ForeignKey` ➡️ [[Departamento]] | Departamento Asignado |
| `foto` | `FileField` | - | foto |
| `creado_en` | `DateTimeField` | - | Fecha de Reporte |
| `fecha_cierre` | `DateTimeField` | - | Fecha de Cierre |
| `actualizado_en` | `DateTimeField` | - | actualizado en |
| `equipo_parado` | `BooleanField` | - | ¿Equipo Parado? (Marque esta opción si la avería ha detenido el funcionamiento del equipo.) |
| `fecha_inicio_parada` | `DateTimeField` | - | Inicio de Parada |
| `fecha_fin_parada` | `DateTimeField` | - | Fin de Parada |


### 🗂️ Modelo `[[FotoAviso]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `aviso` | `ForeignKey` | `ForeignKey` ➡️ [[Aviso]] | aviso |
| `foto` | `FileField` | - | foto |
| `descripcion` | `CharField` | - | Descripción |
| `creado_en` | `DateTimeField` | - | creado en |


### 🗂️ Modelo `[[NotificacionMantenimiento]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `user` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | user |
| `mensaje` | `TextField` | - | mensaje |
| `tipo` | `CharField` | - | tipo |
| `leida` | `BooleanField` | - | leida |
| `creado_en` | `DateTimeField` | - | creado en |


### 🗂️ Modelo `[[OrdenTrabajo]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `codigo_de_orden` | `CharField` | - | Código de Orden |
| `tipo` | `CharField` | - | tipo |
| `prioridad` | `CharField` | - | prioridad |
| `rutina` | `ForeignKey` | `ForeignKey` ➡️ [[Rutina]] | rutina |
| `aviso` | `ForeignKey` | `ForeignKey` ➡️ [[Aviso]] | aviso |
| `tecnico` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | tecnico (Usuario líder (requiere cuenta de sistema)) |
| `tecnico_puesto` | `ForeignKey` | `ForeignKey` ➡️ [[TecnicoPuesto]] | Personal Responsable (Técnico asignado (con o sin usuario)) |
| `empresa_responsable` | `ForeignKey` | `ForeignKey` ➡️ [[Empresa]] | empresa responsable |
| `supervisor` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | supervisor (Supervisor asignado a la orden) |
| `equipo` | `ForeignKey` | `ForeignKey` ➡️ [[Group]] | equipo (Equipo o Grupo de trabajo asignado) |
| `ubicacion` | `ForeignKey` | `ForeignKey` ➡️ [[Ubicacion]] | ubicacion |
| `programacion` | `ForeignKey` | `ForeignKey` ➡️ [[Programacion]] | programacion |
| `falla` | `ForeignKey` | `ForeignKey` ➡️ [[Falla]] | falla |
| `planificacion` | `ForeignKey` | `ForeignKey` ➡️ [[PlanificacionMensual]] | Plan Mensual |
| `inicio_programado` | `DateTimeField` | - | inicio programado (Fecha y hora de inicio prevista) |
| `fin_programado` | `DateTimeField` | - | fin programado (Fecha y hora de fin prevista) |
| `fecha_ejecucion` | `DateTimeField` | - | fecha ejecucion |
| `estado` | `CharField` | - | estado |
| `descripcion_corta` | `CharField` | - | Descripción Corta |
| `descripcion_detallada` | `TextField` | - | Descripción Detallada |
| `notas` | `TextField` | - | notas |
| `equipo_parado` | `BooleanField` | - | ¿Equipo Parado? (Si se marca, el activo pasará a 'Fuera de Servicio' mientras la orden esté abierta) |
| `creado_en` | `DateTimeField` | - | creado en |
| `actualizado_en` | `DateTimeField` | - | actualizado en |
| `requiere_permiso` | `BooleanField` | - | ¿Requiere Permiso? (Si se marca, se exigirá un permiso de trabajo vinculado) |
| `tipo_permiso` | `ForeignKey` | `ForeignKey` ➡️ [[TipoPermiso]] | Tipo de Permiso Sugerido |
| `tecnicos` | `ManyToManyField` | `ManyToManyField` ➡️ [[User]] | tecnicos (Equipo de técnicos asignados (Usuarios)) |
| `colaboradores_puesto` | `ManyToManyField` | `ManyToManyField` ➡️ [[TecnicoPuesto]] | colaboradores puesto (Equipo de técnicos asignados (Personal)) |
| `activos` | `ManyToManyField` | `ManyToManyField` ➡️ [[Activo]] | activos |


### 🗂️ Modelo `[[CierreOrdenTrabajo]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `orden_trabajo` | `OneToOneField` | `OneToOneField` ➡️ [[OrdenTrabajo]] | Orden de Trabajo |
| `tecnico` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | Técnico Responsable |
| `fecha_inicio_real` | `DateTimeField` | - | Inicio Real |
| `fecha_fin_real` | `DateTimeField` | - | Fin Real |
| `horas_hombre` | `FloatField` | - | HH Totales (Total de Horas-Hombre (HH) consumidas) |
| `comentarios` | `TextField` | - | Comentarios Técnicos / Hallazgos |
| `materiales_utilizados` | `TextField` | - | materiales utilizados (Listado de materiales o repuestos utilizados) |
| `creado_en` | `DateTimeField` | - | creado en |
| `actualizado_en` | `DateTimeField` | - | actualizado en |


### 🗂️ Modelo `[[ArchivoOrdenTrabajo]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `orden_trabajo` | `ForeignKey` | `ForeignKey` ➡️ [[OrdenTrabajo]] | orden trabajo |
| `paso` | `ForeignKey` | `ForeignKey` ➡️ [[PasoRutina]] | paso (Paso del checklist al que pertenece esta foto (opcional)) |
| `momento` | `CharField` | - | momento |
| `archivo` | `FileField` | - | archivo |
| `nombre` | `CharField` | - | nombre |
| `tipo` | `CharField` | - | tipo |
| `subido_por` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | subido por |
| `creado_en` | `DateTimeField` | - | creado en |


### 🗂️ Modelo `[[ValorPasoOrden]]`

> **Descripción**: Almacena el resultado/valor capturado para un paso específico de una OT.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `orden_trabajo` | `ForeignKey` | `ForeignKey` ➡️ [[OrdenTrabajo]] | orden trabajo |
| `paso` | `ForeignKey` | `ForeignKey` ➡️ [[PasoRutina]] | paso |
| `valor_texto` | `TextField` | - | valor texto |
| `valor_numerico` | `FloatField` | - | valor numerico |
| `valor_bool` | `BooleanField` | - | valor bool (Para tipos CHECK) |
| `no_aplica` | `BooleanField` | - | no aplica |
| `comentarios` | `TextField` | - | comentarios (Comentarios adicionales del técnico para este paso) |
| `capturado_por` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | capturado por |
| `creado_en` | `DateTimeField` | - | creado en |



---
🔙 Volver a [[00_Inicio|Inicio]]