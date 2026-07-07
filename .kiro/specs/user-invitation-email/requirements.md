# Requirements Document

## Introduction

Esta funcionalidad implementa un flujo de invitación por correo electrónico para nuevos usuarios del sistema. Cuando un administrador registra a un nuevo usuario (proporcionando correo y nombre de usuario), el sistema genera automáticamente un token de invitación único y temporal, y dispara un flujo en Power Automate que envía un correo al usuario con un enlace seguro. Al hacer clic en el enlace, el usuario accede a una página de completado de registro donde puede ingresar sus datos personales y establecer su propia contraseña.

## Glossary

- **Administrator**: Usuario con rol de administrador que tiene permisos para registrar nuevos usuarios en el sistema.
- **Invited_User**: Usuario recién registrado por un administrador que aún no ha completado su perfil ni establecido contraseña.
- **Invitation_Token**: Cadena aleatoria criptográficamente segura, de uso único, asociada a un Invited_User y con tiempo de expiración definido.
- **Invitation_Email**: Correo electrónico enviado al Invited_User que contiene el Invitation_Link.
- **Invitation_Link**: URL única que incluye el Invitation_Token y dirige al Invited_User a la página de completado de registro.
- **Registration_Form**: Formulario web donde el Invited_User completa sus datos personales y establece su contraseña.
- **Power_Automate_Flow**: Flujo automatizado de Microsoft Power Automate responsable del envío del Invitation_Email.
- **Token_Store**: Almacén persistente donde se guardan los Invitation_Tokens junto con su estado, fecha de creación y fecha de expiración.
- **System**: El sistema de gestión de usuarios que coordina el flujo de invitación completo.

---

## Requirements

### Requirement 1: Registro de nuevo usuario por administrador

**User Story:** As an Administrator, I want to register a new user by providing their email and username, so that the system can initiate the invitation flow automatically.

#### Acceptance Criteria

1. WHEN an Administrator submits a new user registration form with a valid email address (RFC 5322 format) and a valid username (1–50 characters, letters/numbers/underscores/hyphens only), THE System SHALL create the user account in a pending-invitation state and SHALL display a confirmation message to the Administrator.
2. IF the email address provided already exists in the system, THEN THE System SHALL reject the registration, return a descriptive validation error indicating the email is already in use, and SHALL preserve all previously submitted form data.
3. IF the username provided already exists in the system, THEN THE System SHALL reject the registration, return a descriptive validation error indicating the username is already taken, and SHALL preserve all previously submitted form data.
4. IF the email address format does not conform to RFC 5322, THEN THE System SHALL reject the registration, return a descriptive validation error indicating the invalid format, and SHALL preserve all previously submitted form data.
5. IF the username does not conform to the allowed format or length (1–50 chars, letters/numbers/underscores/hyphens), THEN THE System SHALL reject the registration and return a descriptive validation error indicating the username format requirements.
6. THE System SHALL persist the new user record with status "pending" before triggering any invitation process.

---

### Requirement 2: Generación del token de invitación

**User Story:** As an Administrator, I want the system to generate a secure and unique invitation token when I register a new user, so that the invitation link cannot be guessed or reused.

#### Acceptance Criteria

1. WHEN a new user account is created in pending-invitation state, THE System SHALL generate a cryptographically random Invitation_Token of at least 32 bytes encoded as a URL-safe string.
2. WHEN the Invitation_Token is generated, THE System SHALL store it in the Token_Store along with the associated user identifier, creation timestamp, expiration timestamp set to 72 hours after creation, and an initial status of "active".
3. WHEN a new Invitation_Token is generated for a user who already has an active token (not expired AND not consumed), THE System SHALL invalidate the prior token before storing the new one.
4. IF a generated Invitation_Token already exists in the Token_Store (collision), THEN THE System SHALL retry token generation up to 3 times; if all retries collide, THE System SHALL return an internal error and abort the user creation flow.
5. THE System SHALL ensure exactly one active Invitation_Token exists per Invited_User at any given time.

---

### Requirement 3: Envío del correo de invitación vía Power Automate

**User Story:** As an Administrator, I want the system to automatically send an invitation email to the new user via Power Automate, so that the user receives a secure link to complete their registration without manual intervention.

#### Acceptance Criteria

1. WHEN an Invitation_Token is successfully stored in the Token_Store, THE System SHALL trigger the Power_Automate_Flow with the Invited_User's email address, username, and the Invitation_Link as input parameters.
2. THE Power_Automate_Flow SHALL send the Invitation_Email to the Invited_User's email address within 5 minutes of being triggered.
3. WHEN the Invitation_Email is delivered, THE Invitation_Email SHALL include the Invitation_Link as a distinctly labelled hyperlink in a dedicated call-to-action section.
4. WHEN the Invitation_Email is delivered, THE Invitation_Email SHALL display the Invited_User's username in the body of the message.
5. WHEN the Invitation_Email is delivered, THE Invitation_Email SHALL state that the Invitation_Link expires after 72 hours.
6. IF the Power_Automate_Flow fails to send the Invitation_Email after 3 retry attempts (60-second intervals), THEN THE System SHALL log the failure with the user identifier, error details, and timestamp, SHALL mark the invitation attempt as failed, and SHALL notify the Administrator of the delivery failure.
7. WHERE the system administrator configures a custom email sender address, THE Power_Automate_Flow SHALL send the Invitation_Email using that configured sender address.
8. IF the Power_Automate_Flow receives missing or invalid input parameters (email, username, or Invitation_Link), THEN THE Power_Automate_Flow SHALL reject the trigger, return a parameter validation error, and THE System SHALL log the malformed request without attempting delivery.

---

### Requirement 4: Construcción del enlace de invitación

**User Story:** As a developer, I want the system to construct a tamper-proof invitation link containing the token, so that the registration page can validate the user's identity before allowing them to complete their profile.

#### Acceptance Criteria

1. WHEN an invitation is generated, THE System SHALL construct the Invitation_Link by appending the Invitation_Token as a query parameter to the configured base registration completion URL.
2. WHEN constructing the Invitation_Link, THE System SHALL reject any base URL that does not begin with `https://` and return a configuration error.
3. WHEN constructing the Invitation_Link, THE System SHALL use the format `{base_url}/complete-registration?token={Invitation_Token}` where `base_url` has no trailing slash and the Invitation_Token is URL-encoded.
4. IF the Invitation_Token is missing or malformed at construction time, THEN THE System SHALL abort the link construction and return an internal error without producing a partial URL.

---

### Requirement 5: Validación del token al acceder al enlace

**User Story:** As an Invited_User, I want the system to validate my invitation link when I click it, so that only I can access my registration form and expired or used links are rejected.

#### Acceptance Criteria

1. WHEN an Invited_User accesses the Invitation_Link, THE System SHALL retrieve the corresponding Invitation_Token from the Token_Store.
2. IF the Invitation_Token does not exist in the Token_Store, THEN THE System SHALL return an error page indicating the link is invalid.
3. IF the Invitation_Token has expired (current timestamp exceeds expiration timestamp), THEN THE System SHALL return an error page indicating the link has expired and SHALL display a navigable control that allows the Invited_User to request a new invitation.
4. IF the Invitation_Token has already been used, THEN THE System SHALL return an error page indicating the link has already been used.
5. WHEN the Invitation_Token is valid AND not expired AND not yet used, THE System SHALL display the Registration_Form pre-filled with the Invited_User's email address and username.
6. IF the Invitation_Link payload is missing the email or username field associated with the token, THEN THE System SHALL return an error page indicating the invitation data is incomplete and SHALL not display the Registration_Form.

---

### Requirement 6: Completado del registro por el usuario

**User Story:** As an Invited_User, I want to fill in my personal data and set my own password through the registration form, so that I can gain full access to the system with my own credentials.

#### Acceptance Criteria

1. WHEN an Invited_User submits the Registration_Form, THE System SHALL validate that all required fields (full name, password, confirm password) are present and non-empty; IF any required field is missing or empty, THEN THE System SHALL return a specific validation error identifying the missing field and SHALL retain all previously entered form data.
2. THE System SHALL require the chosen password to be at least 8 and at most 128 characters long and contain at least one uppercase letter, one lowercase letter, and one number.
3. IF the password does not meet the complexity requirements, THEN THE System SHALL return a validation error message stating "Password must be 8–128 characters and contain at least one uppercase letter, one lowercase letter, and one number" and SHALL retain the previously entered form data except for password fields.
4. IF the confirm password field does not match the password field, THEN THE System SHALL return a validation error message stating "Passwords do not match" and SHALL clear both password fields.
5. WHEN all validations pass, THE System SHALL hash the password using bcrypt (cost factor ≥ 12) or an equivalent secure algorithm before persisting it.
6. WHEN the registration is successfully completed, THE System SHALL update the user account status from "pending" to "active".
7. WHEN the registration is successfully completed, THE System SHALL mark the Invitation_Token as used in the Token_Store.
8. WHEN the registration is successfully completed, THE System SHALL redirect the Invited_User to the application login page.
9. IF the Invitation_Token associated with the Registration_Form submission has already been used (duplicate or replay submission), THEN THE System SHALL reject the submission and return an error page indicating the invitation has already been completed.

---

### Requirement 7: Reenvío de invitación

**User Story:** As an Administrator, I want to resend an invitation email to a pending user, so that users who did not receive or whose link has expired can still complete their registration.

#### Acceptance Criteria

1. WHEN an Administrator requests a resend of the invitation for an Invited_User in "pending" status, THE System SHALL invalidate any existing active Invitation_Token for that Invited_User in the Token_Store before generating a new one; IF the invalidation fails, THEN THE System SHALL abort the resend flow and return an error to the Administrator.
2. WHEN an Administrator requests a resend, THE System SHALL generate a new Invitation_Token following the same rules defined in Requirement 2.
3. WHEN the new Invitation_Token is stored, THE System SHALL trigger the Power_Automate_Flow to send a new Invitation_Email as defined in Requirement 3.
4. IF an Administrator attempts to resend an invitation to a user whose status is not "pending" (e.g., "active", "suspended", "deleted"), THEN THE System SHALL reject the request and return an error indicating the user's current status prevents resending.
5. IF the Power_Automate_Flow dispatch fails after storing the new Invitation_Token during a resend operation, THEN THE System SHALL log the failure with the user identifier, error details, and timestamp, and SHALL notify the Administrator of the delivery failure.

---

### Requirement 8: Expiración automática de tokens no utilizados

**User Story:** As a system operator, I want unused invitation tokens to be automatically invalidated after 72 hours, so that stale invitation links cannot be exploited after their validity period.

#### Acceptance Criteria

1. IF an Invitation_Token exists in the Token_Store AND its expiration timestamp has passed, THEN THE System SHALL treat the token as invalid for any validation request.
2. WHEN the scheduled cleanup process runs, THE System SHALL remove all Invitation_Tokens from the Token_Store whose expiration timestamp has passed and whose status is not "used".
3. IF an Invited_User accesses an Invitation_Link with an expired token, THEN THE System SHALL display an expiry message and a navigable control to request a new invitation link.
4. WHEN an Invitation_Token is created, THE System SHALL set its expiration timestamp to exactly 72 hours after the creation timestamp.
