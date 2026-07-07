# Implementation Plan: user-invitation-email

## Overview

Implementación del flujo completo de invitación por correo electrónico usando Django + Celery + Power Automate. Se crea la app `invitaciones` con sus modelos, servicios, vistas, tareas periódicas y configuración de admin. El flujo abarca: creación de usuario pendiente → generación de token → envío por Power Automate → completado de registro por el usuario.

## Tasks

- [x] 1. Crear la app `invitaciones` y definir modelos
  - Crear la app Django `invitaciones` con `python manage.py startapp invitaciones`
  - Definir `InvitationToken` en `invitaciones/models.py` con campos: `user` (OneToOneField), `token` (CharField unique), `created_at`, `expires_at`, `status`
  - Agregar campo `invitation_status` al modelo `PerfilUsuario` existente (choices: `pending`, `active`, default `active`)
  - Registrar `invitaciones` en `INSTALLED_APPS` y crear/aplicar migraciones
  - _Requirements: 2.2, 2.5, 8.4_

  - [x] 1.1 Crear modelo `InvitationToken` y extensión `PerfilUsuario`
    - Implementar el modelo con `is_valid()` method
    - Generar y aplicar migraciones
    - _Requirements: 2.2, 2.5_

  - [ ]* 1.2 Escribir tests de ejemplo para los modelos
    - Verificar `is_valid()` retorna `True` para token activo no expirado
    - Verificar `is_valid()` retorna `False` para token expirado y para token `used`
    - _Requirements: 2.2, 5.1_

- [x] 2. Implementar jerarquía de excepciones y `TokenService`
  - Crear `invitaciones/exceptions.py` con todas las excepciones tipadas del diseño
  - Implementar `TokenService` en `invitaciones/services.py`:
    - `generate_token(user)`: invalida tokens activos previos, genera bytes criptográficos (≥32 bytes, base64url), persiste con `expires_at = now + 72h`, reintenta hasta 3 veces ante colisión
    - `validate_token(raw_token)`: busca token, lanza `TokenNotFound`, `TokenExpired` o `TokenAlreadyUsed` según estado
    - `consume_token(token)`: marca status como `used`
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 5.1, 5.2, 5.3, 5.4_

  - [x] 2.1 Implementar `TokenService` completo
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [ ]* 2.2 Escribir property test para formato y entropía del token (Property 5)
    - **Property 5: Formato y entropía del token generado**
    - **Validates: Requirements 2.1**

  - [ ]* 2.3 Escribir property test para expiración exacta a 72 horas (Property 6)
    - **Property 6: Expiración exacta a 72 horas**
    - **Validates: Requirements 2.2, 8.4**

  - [ ]* 2.4 Escribir property test para unicidad de token activo por usuario (Property 7)
    - **Property 7: Unicidad de token activo por usuario**
    - **Validates: Requirements 2.3, 2.5**

  - [ ]* 2.5 Escribir property test para token inexistente retorna enlace inválido (Property 10)
    - **Property 10: Token inexistente retorna enlace inválido**
    - **Validates: Requirements 5.2**

  - [ ]* 2.6 Escribir property test para token expirado retorna respuesta de expiración (Property 11)
    - **Property 11: Token expirado retorna respuesta de expiración**
    - **Validates: Requirements 5.3, 8.1**

  - [ ]* 2.7 Escribir property test para token usado retorna respuesta de ya utilizado (Property 12)
    - **Property 12: Token usado retorna respuesta de ya utilizado**
    - **Validates: Requirements 5.4, 6.9**

- [x] 3. Implementar validación de usuarios y `LinkBuilder`
  - Implementar lógica de validación de email (RFC 5322) y username (1–50 chars, `[A-Za-z0-9_\-]`) en `invitaciones/validators.py`
  - Implementar `LinkBuilder` en `invitaciones/services.py`:
    - Lee `BASE_REGISTRATION_URL` de settings
    - Valida que empiece con `https://`
    - Retorna `{base_url}/complete-registration?token={url_encoded_token}`
    - Lanza `ConfigurationError` si la URL base es inválida o el token está vacío
  - _Requirements: 1.4, 1.5, 4.1, 4.2, 4.3, 4.4_

  - [x] 3.1 Implementar `validators.py` con validación de email y username
    - _Requirements: 1.4, 1.5_

  - [ ]* 3.2 Escribir property test para rechazo de emails con formato inválido (Property 3)
    - **Property 3: Rechazo de emails con formato inválido**
    - **Validates: Requirements 1.4**

  - [ ]* 3.3 Escribir property test para rechazo de usernames con formato inválido (Property 4)
    - **Property 4: Rechazo de usernames con formato inválido**
    - **Validates: Requirements 1.5**

  - [x] 3.4 Implementar `LinkBuilder`
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [ ]* 3.5 Escribir property test para formato correcto del Invitation_Link (Property 8)
    - **Property 8: Construcción del Invitation_Link con formato correcto**
    - **Validates: Requirements 4.1, 4.3**

  - [ ]* 3.6 Escribir property test para rechazo de base URL sin HTTPS (Property 9)
    - **Property 9: Rechazo de base URL sin HTTPS**
    - **Validates: Requirements 4.2**

- [ ] 4. Checkpoint — Verificar servicios base
  - Asegurarse de que todos los tests pasan hasta este punto; consultar al usuario si surgen preguntas.

- [ ] 5. Implementar `PowerAutomateInvitationService` y tarea Celery de despacho
  - Implementar `PowerAutomateInvitationService.dispatch()` en `invitaciones/services.py`:
    - Envía POST al webhook configurado en settings con payload `{email, username, invitation_link, sender_email?}`
    - Lanza `PowerAutomateDispatchError` si la respuesta indica fallo
  - Crear `invitaciones/tasks.py` con `dispatch_invitation_email`:
    - `@shared_task(bind=True, max_retries=3)` con `countdown=60` entre reintentos
    - En el callback `on_failure`: loguear `user_id`, error y timestamp; llamar a `notify_admin_of_failure`
  - _Requirements: 3.1, 3.6, 3.7, 3.8_

  - [ ] 5.1 Implementar `PowerAutomateInvitationService`
    - _Requirements: 3.1, 3.7, 3.8_

  - [ ] 5.2 Implementar tarea Celery `dispatch_invitation_email` con reintentos y `on_failure`
    - _Requirements: 3.6_

  - [ ]* 5.3 Escribir tests de integración para la tarea Celery de despacho
    - Verificar que la tarea se encola correctamente tras la creación del usuario
    - Mockear el webhook y verificar el payload enviado
    - _Requirements: 3.1, 3.6_

- [ ] 6. Implementar `InvitationService` (orquestador principal)
  - Implementar `InvitationService` en `invitaciones/services.py`:
    - `create_and_invite(email, username, invited_by)`:
      1. Validar formato de email y username
      2. Verificar unicidad de email y username (lanzar `UserAlreadyExists` si falla)
      3. Crear `User` con `is_active=False` + `PerfilUsuario.invitation_status='pending'`
      4. Llamar a `TokenService.generate_token()`
      5. Llamar a `LinkBuilder.build()`
      6. Encolar `dispatch_invitation_email.delay(user_id, invitation_link)`
      7. Retornar el usuario creado
    - `resend(user, requested_by)`:
      1. Verificar que `user.perfilusuario.invitation_status == 'pending'` (lanzar `InvalidResendTarget` si no)
      2. Invalidar token activo existente
      3. Generar nuevo token y enlace
      4. Encolar nuevo `dispatch_invitation_email`
  - _Requirements: 1.1, 1.2, 1.3, 1.6, 7.1, 7.2, 7.3, 7.4, 7.5_

  - [ ] 6.1 Implementar `create_and_invite` en `InvitationService`
    - _Requirements: 1.1, 1.2, 1.3, 1.6_

  - [ ]* 6.2 Escribir property test para unicidad de email — rechazo de duplicados (Property 1)
    - **Property 1: Unicidad de email — rechazo de duplicados**
    - **Validates: Requirements 1.2**

  - [ ]* 6.3 Escribir property test para unicidad de username — rechazo de duplicados (Property 2)
    - **Property 2: Unicidad de username — rechazo de duplicados**
    - **Validates: Requirements 1.3**

  - [ ] 6.4 Implementar `resend` en `InvitationService`
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [ ]* 6.5 Escribir property test para resend invalida el token anterior y genera uno nuevo (Property 18)
    - **Property 18: Resend invalida el token anterior y genera uno nuevo**
    - **Validates: Requirements 7.1, 7.2**

  - [ ]* 6.6 Escribir property test para rechazo de reenvío para usuarios no pendientes (Property 19)
    - **Property 19: Rechazo de reenvío para usuarios no pendientes**
    - **Validates: Requirements 7.4**

- [ ] 7. Implementar vistas y formulario de completado de registro
  - Crear `invitaciones/forms.py` con `CompleteRegistrationForm`:
    - Campos: `full_name` (requerido), `password` (8–128 chars, ≥1 mayúscula, ≥1 minúscula, ≥1 dígito), `confirm_password`
    - Mensaje de error exacto para contraseña: `"Password must be 8–128 characters and contain at least one uppercase letter, one lowercase letter, and one number"`
    - Mensaje de error exacto para no coincidencia: `"Passwords do not match"`
  - Crear `CompleteRegistrationView` en `invitaciones/views.py`:
    - `GET`: extrae token del query param, valida con `TokenService`, muestra formulario pre-rellenado (email, username) o renderiza página de error correspondiente (`invitation_invalid.html`, `invitation_expired.html`, `invitation_used.html`)
    - `POST`: valida formulario, hashea contraseña con bcrypt (cost ≥12), actualiza usuario (`is_active=True`, `invitation_status='active'`) y consume token en transacción atómica, redirige a login
  - Crear las 3 plantillas de error y la plantilla del formulario de registro
  - Configurar URL `complete-registration/` en `invitaciones/urls.py` e incluir en `urls.py` principal
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9_

  - [ ] 7.1 Implementar `CompleteRegistrationForm` con todas las validaciones
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [ ]* 7.2 Escribir property test para ausencia de campos requeridos en el formulario (Property 13)
    - **Property 13: Ausencia de campos requeridos en el formulario de registro**
    - **Validates: Requirements 6.1**

  - [ ]* 7.3 Escribir property test para rechazo de contraseñas que no cumplen complejidad (Property 14)
    - **Property 14: Rechazo de contraseñas que no cumplen complejidad**
    - **Validates: Requirements 6.2, 6.3**

  - [ ]* 7.4 Escribir property test para rechazo cuando las contraseñas no coinciden (Property 15)
    - **Property 15: Rechazo cuando las contraseñas no coinciden**
    - **Validates: Requirements 6.4**

  - [ ] 7.5 Implementar `CompleteRegistrationView` (GET y POST) con plantillas y URLs
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 6.5, 6.6, 6.7, 6.8, 6.9_

  - [ ]* 7.6 Escribir property test para contraseña almacenada como hash bcrypt (Property 16)
    - **Property 16: Contraseña almacenada como hash bcrypt**
    - **Validates: Requirements 6.5**

  - [ ]* 7.7 Escribir property test para transición de estado del usuario al completar registro (Property 17)
    - **Property 17: Transición de estado del usuario al completar registro**
    - **Validates: Requirements 6.6, 6.7**

  - [ ]* 7.8 Escribir tests de ejemplo para los flujos happy-path de la vista
    - Test de completado exitoso con redirección a login
    - Test de token inválido/expirado/usado muestra página de error correcta
    - _Requirements: 5.3, 6.8_

- [ ] 8. Checkpoint — Verificar flujo completo de registro
  - Asegurarse de que todos los tests pasan hasta este punto; consultar al usuario si surgen preguntas.

- [ ] 9. Implementar tarea Celery de limpieza de tokens expirados
  - Agregar tarea `cleanup_expired_tokens` en `invitaciones/tasks.py`:
    - Elimina `InvitationToken` con `expires_at__lt=now()` y `status != 'used'`
    - Loguea el conteo de tokens eliminados
  - Configurar `CELERY_BEAT_SCHEDULE` con `crontab(hour='*/6')` para esta tarea
  - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [ ] 9.1 Implementar `cleanup_expired_tokens` y configurar Celery Beat
    - _Requirements: 8.1, 8.2_

  - [ ]* 9.2 Escribir property test para limpieza elimina exactamente los tokens expirados no usados (Property 20)
    - **Property 20: Limpieza elimina exactamente los tokens expirados no usados**
    - **Validates: Requirements 8.2**

- [ ] 10. Implementar admin de Django para invitaciones
  - Crear `invitaciones/admin.py`:
    - `InvitationTokenAdmin`: listado con filtros por `status` y `expires_at`
    - Extender `UserAdmin` con acción **"Resend Invitation"** (llama a `InvitationService.resend()`), disponible solo para usuarios con `invitation_status='pending'`
  - Registrar modelos en admin
  - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [ ] 10.1 Implementar `InvitationTokenAdmin` y acción "Resend Invitation" en `UserAdmin`
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [ ]* 10.2 Escribir tests de integración para la acción de reenvío en el admin
    - Verificar que la acción llama a `InvitationService.resend()` correctamente
    - Verificar que la acción no está disponible para usuarios activos
    - _Requirements: 7.4_

- [x] 11. Crear `factories.py` y estructura de tests completa
  - Crear `invitaciones/tests/factories.py` con `factory_boy`:
    - `UserFactory`, `PerfilUsuarioFactory`, `InvitationTokenFactory` (con traits para tokens activos, expirados y usados)
  - Crear `invitaciones/tests/conftest.py` con fixtures de pytest-django (Hypothesis profile para CI)
  - Organizar archivos de test: `test_properties.py`, `test_examples.py`, `test_integration.py`
  - _Requirements: (soporte de infraestructura de testing para todos los requirements)_

  - [x] 11.1 Crear `factories.py` y `conftest.py` con configuración de Hypothesis
    - Perfil CI: `max_examples=100`, `suppress_health_check=[HealthCheck.too_slow]`

- [ ] 12. Checkpoint final — Asegurar cobertura completa
  - Verificar que todas las 20 propiedades están cubiertas por tests de propiedad
  - Ejecutar suite completa; asegurar que todos los tests pasan
  - Consultar al usuario si surgen preguntas.

## Notes

- Las tareas marcadas con `*` son opcionales y pueden omitirse para un MVP más rápido
- Cada tarea referencia requirements específicos para trazabilidad
- Los checkpoints aseguran validación incremental
- Los tests de propiedad (Hypothesis) validan las 20 invariantes universales del diseño
- Los tests de ejemplo validan flujos concretos y casos borde
- La tarea `dispatch_invitation_email` es asíncrona (Celery); mockearla en tests unitarios y verificarla en tests de integración
- La transacción atómica en `CompleteRegistrationView.post()` es crítica: actualización de usuario + consumo de token deben ser atómicos
- El campo `invitation_status` vive en `PerfilUsuario`, no en `auth.User`, para no parchear el modelo de autenticación de Django

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "11.1"] },
    { "id": 1, "tasks": ["1.2", "2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "2.4", "2.5", "2.6", "2.7", "3.1", "3.4"] },
    { "id": 3, "tasks": ["3.2", "3.3", "3.5", "3.6", "5.1"] },
    { "id": 4, "tasks": ["5.2", "6.1", "9.1"] },
    { "id": 5, "tasks": ["5.3", "6.2", "6.3", "6.4", "9.2"] },
    { "id": 6, "tasks": ["6.5", "6.6", "7.1"] },
    { "id": 7, "tasks": ["7.2", "7.3", "7.4", "7.5"] },
    { "id": 8, "tasks": ["7.6", "7.7", "7.8", "10.1"] },
    { "id": 9, "tasks": ["10.2"] }
  ]
}
```
