# 📂 Módulo: Auditorías y Conciliación QR (`auditorias`)

> [!INFO]
> **Etiquetas**: #django/app #auditorias 
> **Propósito**: Auditorias
> **Ubicación en Código**: `file:///d:/Apps/energia/energy/auditorias`

---

## 📦 Modelos de Datos (Base de Datos)

Este módulo gestiona los siguientes modelos en la base de datos. Los campos ForeignKey y relaciones ManyToMany se representan con enlaces `[[ModelName]]` para navegar interactivamente en Obsidian.

### 🗂️ Modelo `[[Auditoria]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | nombre |
| `tipo` | `CharField` | - | tipo |
| `estado` | `CharField` | - | estado |
| `fecha_inicio` | `DateTimeField` | - | fecha inicio |
| `fecha_fin` | `DateTimeField` | - | fecha fin |
| `creado_por` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | creado por |
| `ubicaciones` | `ManyToManyField` | `ManyToManyField` ➡️ [[Ubicacion]] | ubicaciones |
| `categorias` | `ManyToManyField` | `ManyToManyField` ➡️ [[Categoria]] | categorias |


### 🗂️ Modelo `[[ResultadoAuditoria]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `auditoria` | `ForeignKey` | `ForeignKey` ➡️ [[Auditoria]] | auditoria |
| `activo` | `ForeignKey` | `ForeignKey` ➡️ [[Activo]] | activo |
| `estado` | `CharField` | - | estado |
| `ubicacion_esperada` | `ForeignKey` | `ForeignKey` ➡️ [[Ubicacion]] | ubicacion esperada |
| `ubicacion_encontrada` | `ForeignKey` | `ForeignKey` ➡️ [[Ubicacion]] | ubicacion encontrada |
| `fecha_escaneo` | `DateTimeField` | - | fecha escaneo |
| `observaciones` | `TextField` | - | observaciones |
| `sincronizado` | `BooleanField` | - | ¿Movimiento Sincronizado? |
| `sincronizado_por` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | sincronizado por |
| `fecha_sincronizacion` | `DateTimeField` | - | fecha sincronizacion |


### 🗂️ Modelo `[[ConteoAuditoria]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `auditoria` | `ForeignKey` | `ForeignKey` ➡️ [[Auditoria]] | auditoria |
| `ubicacion` | `ForeignKey` | `ForeignKey` ➡️ [[Ubicacion]] | ubicacion |
| `categoria` | `ForeignKey` | `ForeignKey` ➡️ [[Categoria]] | categoria |
| `modelo` | `ForeignKey` | `ForeignKey` ➡️ [[Modelo]] | modelo (Modelo específico de activo (opcional)) |
| `cantidad_esperada` | `PositiveIntegerField` | - | cantidad esperada |
| `cantidad_encontrada` | `PositiveIntegerField` | - | cantidad encontrada |
| `fecha_conteo` | `DateTimeField` | - | fecha conteo |
| `usuario_conteo` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | usuario conteo |
| `observaciones` | `TextField` | - | observaciones |



---
🔙 Volver a [[00_Inicio|Inicio]]