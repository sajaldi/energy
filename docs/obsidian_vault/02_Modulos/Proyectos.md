# 📂 Módulo: Gestión de Proyectos (CAPEX) (`proyectos`)

> [!INFO]
> **Etiquetas**: #django/app #proyectos 
> **Propósito**: Proyectos
> **Ubicación en Código**: `file:///d:/Apps/energia/energy/proyectos`

---

## 📦 Modelos de Datos (Base de Datos)

Este módulo gestiona los siguientes modelos en la base de datos. Los campos ForeignKey y relaciones ManyToMany se representan con enlaces `[[ModelName]]` para navegar interactivamente en Obsidian.

### 🗂️ Modelo `[[Proyecto]]`

> **Descripción**: Modelo principal de Proyecto.
    Contiene documentos y actividades asociadas.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `codigo` | `CharField` | - | codigo (Código único del proyecto (se genera automáticamente si se deja vacío, formato: PROY-YYYY-NNNN)) |
| `nombre` | `CharField` | - | nombre |
| `descripcion` | `TextField` | - | descripcion |
| `nota` | `TextField` | - | nota (Notas internas del proyecto) |
| `estado` | `CharField` | - | estado |
| `fecha_inicio` | `DateField` | - | fecha inicio |
| `fecha_fin_estimada` | `DateField` | - | fecha fin estimada |
| `responsable` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | responsable |
| `ubicacion` | `ForeignKey` | `ForeignKey` ➡️ [[Ubicacion]] | ubicacion |
| `creado_en` | `DateTimeField` | - | creado en |
| `actualizado_en` | `DateTimeField` | - | actualizado en |
| `visores` | `ManyToManyField` | `ManyToManyField` ➡️ [[VisorPlano]] | visores (Visores de plano para ubicar actividades del proyecto) |


### 🗂️ Modelo `[[DocumentoProyecto]]`

> **Descripción**: Relación entre Proyecto y Documento.
    Permite agregar documentos como inline en el admin.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `proyecto` | `ForeignKey` | `ForeignKey` ➡️ [[Proyecto]] | proyecto |
| `documento` | `ForeignKey` | `ForeignKey` ➡️ [[Documento]] | documento |
| `carpeta` | `ForeignKey` | `ForeignKey` ➡️ [[Carpeta]] | carpeta |
| `nota` | `CharField` | - | nota (Nota o descripción del documento en este proyecto) |
| `agregado_en` | `DateTimeField` | - | agregado en |


### 🗂️ Modelo `[[Actividad]]`

> **Descripción**: Actividad dentro de un proyecto.
    Puede ser ubicada en un pin de plano.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `proyecto` | `ForeignKey` | `ForeignKey` ➡️ [[Proyecto]] | proyecto |
| `nombre` | `CharField` | - | nombre |
| `descripcion` | `TextField` | - | descripcion |
| `estado` | `CharField` | - | estado |
| `prioridad` | `CharField` | - | prioridad |
| `fecha_inicio` | `DateField` | - | fecha inicio |
| `fecha_fin` | `DateField` | - | fecha fin |
| `porcentaje_avance` | `PositiveIntegerField` | - | porcentaje avance (Porcentaje de avance (0-100)) |
| `asignado_a` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | asignado a |
| `predecesora` | `ForeignKey` | `ForeignKey` ➡️ [[Actividad]] | Actividad Predecesora |
| `orden` | `PositiveIntegerField` | - | orden (Orden de ejecución) |
| `color` | `CharField` | - | color (Color para identificar en planos) |
| `creado_en` | `DateTimeField` | - | creado en |
| `actualizado_en` | `DateTimeField` | - | actualizado en |



---
🔙 Volver a [[00_Inicio|Inicio]]