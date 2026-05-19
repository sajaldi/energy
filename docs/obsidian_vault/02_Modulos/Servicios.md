# 📂 Módulo: Servicios y KPIs (`servicios`)

> [!INFO]
> **Etiquetas**: #django/app #servicios 
> **Propósito**: Servicios
> **Ubicación en Código**: `file:///d:/Apps/energia/energy/servicios`

---

## 📦 Modelos de Datos (Base de Datos)

Este módulo gestiona los siguientes modelos en la base de datos. Los campos ForeignKey y relaciones ManyToMany se representan con enlaces `[[ModelName]]` para navegar interactivamente en Obsidian.

### 🗂️ Modelo `[[Servicio]]`

> **Descripción**: Modelo para gestionar servicios

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | nombre |
| `descripcion` | `TextField` | - | descripcion |
| `codigo` | `CharField` | - | codigo |
| `activo` | `BooleanField` | - | activo |
| `fecha_creacion` | `DateTimeField` | - | fecha creacion |
| `fecha_actualizacion` | `DateTimeField` | - | fecha actualizacion |


### 🗂️ Modelo `[[KPI]]`

> **Descripción**: Modelo para Key Performance Indicators (Indicadores Clave de Desempeño)

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `servicio` | `ForeignKey` | `ForeignKey` ➡️ [[Servicio]] | servicio |
| `nombre` | `CharField` | - | nombre |
| `descripcion` | `TextField` | - | descripcion |
| `forma_de_cumplimiento` | `TextField` | - | forma de cumplimiento (Forma de cumplimiento (Texto)) |
| `metodo_de_supervision` | `TextField` | - | metodo de supervision (Método de Supervisión (Texto)) |
| `categoria` | `CharField` | - | categoria |
| `estado` | `CharField` | - | estado |
| `comentarios` | `TextField` | - | Comentarios adicionales |
| `fecha_medicion` | `DateField` | - | fecha medicion |
| `fecha_creacion` | `DateTimeField` | - | fecha creacion |
| `fecha_actualizacion` | `DateTimeField` | - | fecha actualizacion |
| `embedding` | `VectorField` | - | embedding |
| `rutinas` | `ManyToManyField` | `ManyToManyField` ➡️ [[Rutina]] | rutinas (Rutinas de mantenimiento vinculadas a este KPI) |


### 🗂️ Modelo `[[ChecklistItem]]`

> **Descripción**: Elemento de checklist asociado a un KPI.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `kpi` | `ForeignKey` | `ForeignKey` ➡️ [[KPI]] | kpi |
| `descripcion` | `CharField` | - | descripcion |
| `completado` | `BooleanField` | - | completado |
| `orden` | `PositiveIntegerField` | - | orden |


### 🗂️ Modelo `[[Auditoria]]`

> **Descripción**: Modelo para representar una auditoría de KPIs.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | nombre (Nombre de la auditoría (Ej: Auditoría Trimestral Q1 2026)) |
| `fecha` | `DateField` | - | fecha |
| `descripcion` | `TextField` | - | descripcion |
| `fecha_creacion` | `DateTimeField` | - | fecha creacion |
| `fecha_actualizacion` | `DateTimeField` | - | fecha actualizacion |


### 🗂️ Modelo `[[AuditoriaResultado]]`

> **Descripción**: Resultado del desempeño de un KPI en una auditoría específica.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `auditoria` | `ForeignKey` | `ForeignKey` ➡️ [[Auditoria]] | auditoria |
| `kpi` | `ForeignKey` | `ForeignKey` ➡️ [[KPI]] | kpi |
| `cumple` | `BooleanField` | - | ¿Cumple? |
| `plan_de_accion` | `TextField` | - | Plan de Acción |
| `observaciones` | `TextField` | - | observaciones |


### 🗂️ Modelo `[[KPIFragmento]]`

> **Descripción**: Fragmento vectorizado de un KPI para búsqueda semántica RAG.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `kpi` | `ForeignKey` | `ForeignKey` ➡️ [[KPI]] | kpi |
| `contenido` | `TextField` | - | contenido (Texto compuesto del KPI para búsqueda semántica) |
| `embedding` | `VectorField` | - | embedding |
| `orden` | `IntegerField` | - | orden |



---
🔙 Volver a [[00_Inicio|Inicio]]