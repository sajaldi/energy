# 📂 Módulo: Mapeo IoT y Mediciones en Tiempo Real (`iot`)

> [!INFO]
> **Etiquetas**: #django/app #iot 
> **Propósito**: Iot
> **Ubicación en Código**: `file:///d:/Apps/energia/energy/iot`

---

## 📦 Modelos de Datos (Base de Datos)

Este módulo gestiona los siguientes modelos en la base de datos. Los campos ForeignKey y relaciones ManyToMany se representan con enlaces `[[ModelName]]` para navegar interactivamente en Obsidian.

### 🗂️ Modelo `[[BACnetGateway]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | nombre |
| `ip_address` | `GenericIPAddressField` | - | ip address (IP local del servidor para el socket BACnet (o IP VPN)) |
| `port` | `IntegerField` | - | port |
| `device_id` | `IntegerField` | - | device id (Device ID de este servidor en la red BACnet) |
| `is_active` | `BooleanField` | - | is active |
| `last_sync` | `DateTimeField` | - | last sync |


### 🗂️ Modelo `[[BACnetDevice]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `gateway` | `ForeignKey` | `ForeignKey` ➡️ [[BACnetGateway]] | gateway |
| `device_id` | `IntegerField` | - | device id |
| `name` | `CharField` | - | name |
| `address` | `CharField` | - | address (IP remota del controlador) |
| `vendor` | `CharField` | - | vendor |
| `model_name` | `CharField` | - | model name |
| `is_online` | `BooleanField` | - | is online |
| `last_seen` | `DateTimeField` | - | last seen |


### 🗂️ Modelo `[[BACnetPoint]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `device` | `ForeignKey` | `ForeignKey` ➡️ [[BACnetDevice]] | device |
| `name` | `CharField` | - | name |
| `object_type` | `CharField` | - | object type |
| `instance` | `IntegerField` | - | instance |
| `description` | `TextField` | - | description |
| `unit` | `CharField` | - | unit |
| `save_history` | `BooleanField` | - | save history |


### 🗂️ Modelo `[[Telemetry]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `point` | `ForeignKey` | `ForeignKey` ➡️ [[BACnetPoint]] | point |
| `timestamp` | `DateTimeField` | - | timestamp |
| `value` | `FloatField` | - | value |
| `status` | `CharField` | - | status |


### 🗂️ Modelo `[[BACnetSchedule]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `device` | `ForeignKey` | `ForeignKey` ➡️ [[BACnetDevice]] | device |
| `name` | `CharField` | - | name |
| `instance` | `IntegerField` | - | instance |
| `weekly_schedule` | `JSONField` | - | weekly schedule (JSON representation of weekly events) |
| `present_value` | `BooleanField` | - | present value |
| `last_sync` | `DateTimeField` | - | last sync |



---
🔙 Volver a [[00_Inicio|Inicio]]