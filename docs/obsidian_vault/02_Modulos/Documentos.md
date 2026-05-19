# 📂 Módulo: Gestión Documental (`documentos`)

> [!INFO]
> **Etiquetas**: #django/app #documentos 
> **Propósito**: Documentos
> **Ubicación en Código**: `file:///d:/Apps/energia/energy/documentos`

---

## 📦 Modelos de Datos (Base de Datos)

Este módulo gestiona los siguientes modelos en la base de datos. Los campos ForeignKey y relaciones ManyToMany se representan con enlaces `[[ModelName]]` para navegar interactivamente en Obsidian.

### 🗂️ Modelo `[[TipoDocumento]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | nombre |
| `codigo` | `CharField` | - | codigo (Abreviatura para códigos (ej: PLN, MNL)) |


### 🗂️ Modelo `[[Carpeta]]`

> **Descripción**: Sistema de carpetas jerárquicas para organizar documentos en todo el sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | nombre |
| `padre` | `ForeignKey` | `ForeignKey` ➡️ [[Carpeta]] | padre |
| `proyecto_id` | `IntegerField` | - | proyecto id (ID del proyecto vinculado (si aplica)) |
| `creado_en` | `DateTimeField` | - | creado en |
| `departamentos` | `ManyToManyField` | `ManyToManyField` ➡️ [[Departamento]] | departamentos (Si se asignan departamentos, solo los usuarios de esos departamentos verán esta carpeta.) |


### 🗂️ Modelo `[[MetadatoConfig]]`

> **Descripción**: Configuración de campos dinámicos asociados a un Tipo de Documento.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `tipo_documento` | `ForeignKey` | `ForeignKey` ➡️ [[TipoDocumento]] | tipo documento |
| `nombre` | `CharField` | - | nombre (Nombre interno del campo (ej: fecha_vencimiento)) |
| `etiqueta` | `CharField` | - | etiqueta (Nombre que verá el usuario (ej: Fecha de Vencimiento)) |
| `tipo_campo` | `CharField` | - | tipo campo |
| `requerido` | `BooleanField` | - | requerido |
| `modelo_relativo` | `ForeignKey` | `ForeignKey` ➡️ [[ContentType]] | modelo relativo (Si el tipo es RELACION, seleccione a qué tabla apunta.) |
| `campo_visualizacion` | `CharField` | - | campo visualizacion (Si el tipo es RELACION, nombre del campo a mostrar (ej: 'nombre', 'codigo'). Dejar vacío para usar el valor por defecto.) |
| `descripcion` | `TextField` | - | descripcion (Instrucciones para la IA: dónde o cómo extraer este campo del documento (ej: 'Buscar en el encabezado, después de Asunto:')) |
| `orden` | `PositiveIntegerField` | - | orden |


### 🗂️ Modelo `[[Disciplina]]`

> **Descripción**: Modelo maestro del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | nombre |
| `codigo` | `CharField` | - | codigo (Abreviatura (ej: ELE, MEC)) |


### 🗂️ Modelo `[[N8nChatHistory]]`

> **Descripción**: Historial de conversaciones con el chat de IA (n8n).
    Almacena mensajes del usuario y respuestas de la IA para mantener contexto.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `session_id` | `CharField` | - | session id (ID de sesión para agrupar mensajes de una conversación) |
| `usuario` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | usuario |
| `documento` | `ForeignKey` | `ForeignKey` ➡️ [[Documento]] | documento (Documento sobre el que se está conversando (opcional)) |
| `mensaje_usuario` | `TextField` | - | mensaje usuario (Pregunta o mensaje del usuario) |
| `respuesta_ia` | `TextField` | - | respuesta ia (Respuesta generada por la IA) |
| `timestamp` | `DateTimeField` | - | timestamp |
| `tokens_usados` | `IntegerField` | - | tokens usados (Tokens consumidos en esta interacción) |
| `modelo` | `CharField` | - | modelo (Modelo de IA utilizado (ej: gpt-4)) |


### 🗂️ Modelo `[[Documento]]`

> **Descripción**: Documento Maestro. 
    Representa la entidad abstracta del documento.
    Apunta siempre a la última revisión válida.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `codigo` | `CharField` | - | Código (Código único del documento (Ej: CCG-I-T1-IAA-07-02)) |
| `titulo` | `CharField` | - | Título |
| `tipo_documento` | `ForeignKey` | `ForeignKey` ➡️ [[TipoDocumento]] | Tipo |
| `disciplina` | `ForeignKey` | `ForeignKey` ➡️ [[Disciplina]] | disciplina |
| `respuesta_a` | `ForeignKey` | `ForeignKey` ➡️ [[Documento]] | Respuesta a (Documento al que este archivo hace referencia o responde.) |
| `estado_actual` | `CharField` | - | estado actual |
| `responsable` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | Responsable |
| `ultima_revision` | `ForeignKey` | `ForeignKey` ➡️ [[Revision]] | Última Revisión |
| `creado_en` | `DateTimeField` | - | creado en |
| `actualizado_en` | `DateTimeField` | - | actualizado en |
| `carpeta` | `ForeignKey` | `ForeignKey` ➡️ [[Carpeta]] | carpeta |
| `contenido_texto` | `TextField` | - | Contenido Texto (Texto extraído del documento para búsquedas.) |
| `fecha_inicio` | `DateField` | - | Fecha Inicio/Emisión (Fecha de inicio o emisión del documento.) |
| `fecha_vencimiento` | `DateField` | - | Fecha de Vencimiento (Fecha en que expira la validez del documento.) |
| `embedding` | `VectorField` | - | embedding |
| `activos` | `ManyToManyField` | `ManyToManyField` ➡️ [[Activo]] | activos |
| `ubicaciones` | `ManyToManyField` | `ManyToManyField` ➡️ [[Ubicacion]] | ubicaciones |
| `departamentos` | `ManyToManyField` | `ManyToManyField` ➡️ [[Departamento]] | departamentos (Si se asignan departamentos, solo los usuarios de esos departamentos verán este documento.) |


### 🗂️ Modelo `[[DocumentoFragmento]]`

> **Descripción**: Representa un fragmento de texto de un documento para búsqueda vectorial.
    Permite indexar documentos largos dividiéndolos en partes más pequeñas.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `documento` | `ForeignKey` | `ForeignKey` ➡️ [[Documento]] | documento |
| `contenido` | `TextField` | - | contenido |
| `embedding` | `VectorField` | - | embedding |
| `orden` | `IntegerField` | - | orden |


### 🗂️ Modelo `[[MetadatoValor]]`

> **Descripción**: Almacena el valor de un metadato dinámico para un documento específico.
    Soporta valores de texto y vínculos relacionales genéricos.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `documento` | `ForeignKey` | `ForeignKey` ➡️ [[Documento]] | documento |
| `config` | `ForeignKey` | `ForeignKey` ➡️ [[MetadatoConfig]] | config |
| `valor` | `TextField` | - | valor |
| `content_type` | `ForeignKey` | `ForeignKey` ➡️ [[ContentType]] | content type |
| `object_id` | `PositiveIntegerField` | - | object id |


### 🗂️ Modelo `[[ComentarioDocumento]]`

> **Descripción**: Comentarios u observaciones asociados a un punto específico del PDF.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `documento` | `ForeignKey` | `ForeignKey` ➡️ [[Documento]] | documento |
| `revision` | `ForeignKey` | `ForeignKey` ➡️ [[Revision]] | revision |
| `usuario` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | usuario |
| `texto` | `TextField` | - | texto |
| `tipo` | `CharField` | - | tipo |
| `posicion_x` | `FloatField` | - | posicion x (Posición X en porcentaje (0-100)) |
| `posicion_y` | `FloatField` | - | posicion y (Posición Y en porcentaje (0-100)) |
| `ancho` | `FloatField` | - | ancho (Ancho en porcentaje (0-100) para áreas) |
| `alto` | `FloatField` | - | alto (Alto en porcentaje (0-100) para áreas) |
| `pagina` | `PositiveIntegerField` | - | pagina |
| `creado_en` | `DateTimeField` | - | creado en |
| `resuelto` | `BooleanField` | - | resuelto (Marcar si el comentario ya ha sido atendido) |
| `responsable` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | responsable (Usuario asignado para resolver este comentario) |
| `vinculos` | `ManyToManyField` | `ManyToManyField` ➡️ [[ComentarioDocumento]] | vinculos (Pines relacionados en otros documentos) |


### 🗂️ Modelo `[[ComentarioImagen]]`

> **Descripción**: Imágenes o fotos adjuntas a un comentario/pin.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `comentario` | `ForeignKey` | `ForeignKey` ➡️ [[ComentarioDocumento]] | comentario |
| `imagen` | `FileField` | - | imagen |
| `creado_en` | `DateTimeField` | - | creado en |


### 🗂️ Modelo `[[Revision]]`

> **Descripción**: Revisiones históricas del documento.
    Cada carga de archivo genera una nueva instancia aquí.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `documento` | `ForeignKey` | `ForeignKey` ➡️ [[Documento]] | documento |
| `revision` | `CharField` | - | Revisión (Ej: A, B, 0, 1, 2...) |
| `archivo` | `FileField` | - | archivo |
| `fecha_revision` | `DateField` | - | fecha revision |
| `creado_por` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | creado por |
| `creado_en` | `DateTimeField` | - | creado en |
| `comentarios` | `TextField` | - | comentarios (Descripción del cambio) |
| `hash_archivo` | `CharField` | - | hash archivo |
| `estado_extraccion` | `CharField` | - | estado extraccion |
| `datos_extraidos` | `JSONField` | - | datos extraidos |


### 🗂️ Modelo `[[Biblioteca]]`

> **Descripción**: Colección de documentos agrupados temáticamente.
    Relación muchos a muchos con Documento.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `nombre` | `CharField` | - | Nombre |
| `descripcion` | `TextField` | - | Descripción |
| `resumen_ia` | `TextField` | - | Resumen IA (Resultado guardado del análisis automatizado de todos los documentos.) |
| `creado_por` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | Creado por |
| `creado_en` | `DateTimeField` | - | creado en |
| `actualizado_en` | `DateTimeField` | - | actualizado en |
| `documentos` | `ManyToManyField` | `ManyToManyField` ➡️ [[Documento]] | Documentos |


### 🗂️ Modelo `[[ComentarioBiblioteca]]`

> **Descripción**: Notas o comentarios adicionales asociados a una biblioteca.
    Sirven como insumo extra para el análisis de IA.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `biblioteca` | `ForeignKey` | `ForeignKey` ➡️ [[Biblioteca]] | biblioteca |
| `titulo` | `CharField` | - | Título |
| `contenido` | `TextField` | - | Contenido |
| `fecha` | `DateTimeField` | - | fecha |


### 🗂️ Modelo `[[PerfilFirma]]`

> **Descripción**: Perfil de firma de un usuario.
    Permite almacenar una firma manuscrita o subida como PNG
    para reutilización en múltiples documentos.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `usuario` | `OneToOneField` | `OneToOneField` ➡️ [[User]] | Usuario |
| `firma_imagen` | `FileField` | - | firma imagen (Imagen de la firma (PNG recomendado con fondo transparente)) |
| `creada_en` | `DateTimeField` | - | creada en |
| `actualizada_en` | `DateTimeField` | - | actualizada en |
| `activa` | `BooleanField` | - | activa (Si está activa, esta firma se usará por defecto) |
| `cargo` | `CharField` | - | cargo (Cargo del firmante) |
| `departamento` | `CharField` | - | departamento |


### 🗂️ Modelo `[[DocumentoFirmado]]`

> **Descripción**: Representa un documento que ha sido firmado.
    Contiene el hash del documento original para verificación de integridad.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `documento` | `ForeignKey` | `ForeignKey` ➡️ [[Documento]] | Documento |
| `revision` | `ForeignKey` | `ForeignKey` ➡️ [[Revision]] | Revisión del Documento |
| `hash_documento_original` | `CharField` | - | hash documento original (Hash SHA-256 del documento en el momento de la firma) |
| `estado` | `CharField` | - | estado |
| `creado_en` | `DateTimeField` | - | creado en |
| `actualizado_en` | `DateTimeField` | - | actualizado en |
| `pdf_firmado` | `FileField` | - | pdf firmado (PDF con todas las firmas estampadas) |


### 🗂️ Modelo `[[FirmaRequerida]]`

> **Descripción**: Define los firmantes requeridos para un documento.
    Workflow de aprobación: Especifica quién debe firmar y en qué orden.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `documento_firmado` | `ForeignKey` | `ForeignKey` ➡️ [[DocumentoFirmado]] | Documento |
| `firmante` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | Firmante Requerido |
| `orden` | `IntegerField` | - | orden (Orden en que debe firmarse (1 = primero). 0 = sin orden específico) |
| `rol` | `CharField` | - | rol (Ej: 'Elaboró', 'Revisó', 'Aprobó', 'Autorizó') |
| `posicion_x` | `FloatField` | - | posicion x (Posición X en el documento (porcentaje 0-100)) |
| `posicion_y` | `FloatField` | - | posicion y (Posición Y en el documento (porcentaje 0-100)) |
| `pagina` | `IntegerField` | - | pagina (Número de página donde se estampará la firma) |
| `ancho` | `FloatField` | - | ancho (Ancho de la firma (% del ancho de página)) |
| `alto` | `FloatField` | - | alto (Alto de la firma (% del alto de página)) |
| `obligatoria` | `BooleanField` | - | obligatoria (Si es obligatoria, el documento no se completa sin esta firma) |
| `notificado` | `BooleanField` | - | notificado (Si se ha notificado al firmante) |
| `fecha_notificacion` | `DateTimeField` | - | fecha notificacion |


### 🗂️ Modelo `[[Firma]]`

> **Descripción**: Registro de una firma electrónica aplicada a un documento.
    Contiene toda la información de trazabilidad y seguridad.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `documento_firmado` | `ForeignKey` | `ForeignKey` ➡️ [[DocumentoFirmado]] | Documento Firmado |
| `firma_requerida` | `OneToOneField` | `OneToOneField` ➡️ [[FirmaRequerida]] | Firma Requerida |
| `firmante` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | Firmante |
| `imagen_firma` | `FileField` | - | imagen firma (Imagen PNG de la firma estampada) |
| `posicion_x` | `FloatField` | - | posicion x (Coordenada X (porcentaje)) |
| `posicion_y` | `FloatField` | - | posicion y (Coordenada Y (porcentaje)) |
| `pagina` | `IntegerField` | - | pagina (Número de página) |
| `ancho` | `FloatField` | - | ancho |
| `alto` | `FloatField` | - | alto |
| `fecha_firma` | `DateTimeField` | - | fecha firma |
| `ip_firmante` | `GenericIPAddressField` | - | ip firmante (Dirección IP desde donde se firmó) |
| `user_agent` | `TextField` | - | user agent (Navegador/dispositivo usado para firmar) |
| `hash_firma` | `CharField` | - | hash firma (Hash SHA-256 de la imagen de firma) |
| `token_verificacion` | `UUIDField` | - | token verificacion (Token único para verificar la autenticidad de la firma) |
| `firmado` | `BooleanField` | - | firmado |
| `rechazado` | `BooleanField` | - | rechazado |
| `motivo_rechazo` | `TextField` | - | motivo rechazo |
| `comentarios` | `TextField` | - | comentarios (Comentarios del firmante) |


### 🗂️ Modelo `[[AuditoriaFirmas]]`

> **Descripción**: Log de auditoría para todas las acciones relacionadas con firmas.
    Proporciona trazabilidad completa del sistema.

| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |
| :--- | :--- | :--- | :--- |
| `id` | `BigAutoField` | - | ID |
| `usuario` | `ForeignKey` | `ForeignKey` ➡️ [[User]] | usuario |
| `accion` | `CharField` | - | accion |
| `documento_firmado` | `ForeignKey` | `ForeignKey` ➡️ [[DocumentoFirmado]] | documento firmado |
| `firma` | `ForeignKey` | `ForeignKey` ➡️ [[Firma]] | firma |
| `fecha` | `DateTimeField` | - | fecha |
| `ip` | `GenericIPAddressField` | - | ip |
| `detalles` | `JSONField` | - | detalles |



---
🔙 Volver a [[00_Inicio|Inicio]]