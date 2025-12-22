# Sistema de Comunicaciones (Aconex Style) - Guía de Uso

Este módulo permite gestionar la correspondencia formal del proyecto con total trazabilidad.

## 1. Configuración de Tipos
Primero, define qué tipos de correo usarás en **Comunicaciones > Tipos de Comunicado**:
*   **RFI**: Request for Information (ID: `RFI`).
*   **TRN**: Transmittal de Documentos (ID: `TRN`).
*   **INST**: Instrucción de Campo (ID: `INST`).

## 2. Redactar un Comunicación (Borrador)
1.  Ve a **Comunicaciones > Comunicados** y haz clic en **Agregar**.
2.  Selecciona el **Tipo** y escribe un **Asunto**.
3.  Escribe el contenido en el **Cuerpo**.
4.  El estado inicial es `BORRADOR`. En este estado puedes editarlo cuantas veces quieras.
5.  **Destinatarios**: En la lista de abajo, agrega a los usuarios que deben recibir el mensaje (Tipo: Para, CC o CCO).
6.  **Adjuntos**: Puedes adjuntar archivos sueltos o **versiones específicas de documentos** del sistema anterior (Transmittals).

## 3. Envío Oficial (Inmutabilidad)
Una vez el borrador esté listo:
1.  En la lista de Comunicados, selecciona el registro.
2.  En el menú de "Acciones", elige **"Enviar comunicados seleccionados"** y dale a "Ir".
3.  **Resultado**: 
    *   Se le asignará un **Consecutivo único** (ej: `RFI-001-2025`).
    *   Se fijará la **Fecha de Envío**.
    *   El correo pasará a ser **Inmutable** (ya no podrás editarlo ni borrarlo, garantizando la auditoría).

### 4. Notificaciones y Trazabilidad
Cada vez que un correo pasa a estado **Enviado**:
*   **Notificación Interna**: Se crea un registro en **Comunicaciones > Notificaciones** para cada destinatario.
*   **Email**: Si el usuario tiene un correo configurado, el sistema le enviará un aviso automático con el asunto y el remitente.
*   **Tracking**: Podrás ver quién ha leído el mensaje en la sección de Destinatarios del comunicado.

---
**Nota**: El sistema registra automáticamente quién envió el correo basándose en el usuario logueado.
