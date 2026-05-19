# 📂 Módulo: Comunicaciones e Hilos (Transmittals) (`comunicaciones`)

> [!INFO]
> **Etiquetas**: #django/app #comunicaciones 
> **Propósito**: Comunicaciones
> **Ubicación en Código**: `file:///d:/Apps/energia/energy/comunicaciones`

---

## 📦 Modelos de Datos (Base de Datos)

Este módulo gestiona los siguientes modelos en la base de datos. Los campos ForeignKey y relaciones ManyToMany se representan con enlaces `[[ModelName]]` para navegar interactivamente en Obsidian.

### 🗂️ Modelo `[[TipoComunicado]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | nombre |
| `codigo` | `CharField` | - | codigo (Prefijo para consecutivo (ej: RFI, MEMO)) |


### 🗂️ Modelo `[[Comunicado]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `tipo` | `ForeignKey` | `ForeignKey` ➡️ [[TipoComunicado]] | tipo |
| `consecutivo` | `CharField` | - | consecutivo |
| `asunto` | `CharField` | - | asunto |
| `cuerpo` | `TextField` | - | cuerpo (Contenido del mensaje) |
| `remitente` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | remitente |
| `fecha_envio` | `DateTimeField` | - | fecha envio |
| `estado` | `CharField` | - | estado |
| `parent` | `ForeignKey` | `ForeignKey` ➡️ [[Comunicado]] | parent |
| `creado_en` | `DateTimeField` | - | creado en |
| `actualizado_en` | `DateTimeField` | - | actualizado en |


### 🗂️ Modelo `[[Destinatario]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `comunicado` | `ForeignKey` | `ForeignKey` ➡️ [[Comunicado]] | comunicado |
| `usuario` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | usuario |
| `tipo` | `CharField` | - | tipo |
| `leido` | `BooleanField` | - | leido |
| `fecha_leido` | `DateTimeField` | - | fecha leido |


### 🗂️ Modelo `[[AdjuntoComunicado]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `comunicado` | `ForeignKey` | `ForeignKey` ➡️ [[Comunicado]] | comunicado |
| `documento_revision` | `ForeignKey` | `ForeignKey` ➡️ [[Revision]] | documento revision |
| `archivo` | `FileField` | - | archivo |
| `activo` | `ForeignKey` | `ForeignKey` ➡️ [[Activo]] | activo |


### 🗂️ Modelo `[[Notificacion]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `usuario` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | usuario |
| `comunicado` | `ForeignKey` | `ForeignKey` ➡️ [[Comunicado]] | comunicado |
| `leida` | `BooleanField` | - | leida |
| `fecha_creacion` | `DateTimeField` | - | fecha creacion |


### 🗂️ Modelo `[[BotSession]]`

> **Descripción**: Control de estado de los usuarios para el bot de WhatsApp.
    Mapea la tabla bot_sessions requerida para el flujo de n8n.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `phone_number` | `CharField` | - | phone number |
| `status` | `CharField` | - | status |
| `context` | `JSONField` | - | context (Datos temporales de la sesión (ej. en medio de un wizard)) |
| `last_update` | `DateTimeField` | - | last update |



---
🔙 Volver a [[00_Inicio|Inicio]]