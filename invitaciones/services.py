"""
Servicios del módulo de invitaciones.

Clases:
  - TokenService  : generación, validación y consumo de InvitationToken.
  - LinkBuilder   : construcción del Invitation_Link.
  - PowerAutomateInvitationService : disparo del webhook de Power Automate.
  - InvitationService : orquestador del flujo completo de invitación.
"""

import logging
import secrets
from datetime import timedelta
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from .exceptions import (
    ConfigurationError,
    InvalidResendTarget,
    PowerAutomateDispatchError,
    TokenAlreadyUsed,
    TokenCollisionError,
    TokenExpired,
    TokenNotFound,
)
from .models import InvitationToken

logger = logging.getLogger(__name__)
User = get_user_model()


class TokenService:
    """
    Gestiona el ciclo de vida de los InvitationToken:
    generación criptográfica, validación y consumo.
    """

    TOKEN_EXPIRY_HOURS = 72
    MAX_RETRIES = 3

    # ------------------------------------------------------------------
    # Generación
    # ------------------------------------------------------------------

    def generate_token(self, user: User) -> InvitationToken:
        """
        Invalida tokens activos previos del usuario, genera un token
        criptográficamente seguro (≥32 bytes, URL-safe base64) y persiste
        el nuevo registro con:
          - expires_at = now() + 72 h
          - status = 'active'

        Reintenta hasta MAX_RETRIES veces si hay colisión de valor de token.
        Lanza TokenCollisionError si todos los reintentos fallan.

        Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5
        """
        # Paso 1 – Invalidar tokens activos previos del usuario.
        InvitationToken.objects.filter(user=user, status='active').update(status='invalid')

        # Paso 2 y 3 – Generar candidato y verificar unicidad (con reintentos).
        candidate = None
        for attempt in range(self.MAX_RETRIES):
            raw = secrets.token_urlsafe(32)
            if not InvitationToken.objects.filter(token=raw).exists():
                candidate = raw
                break
            logger.warning(
                "TokenService: colisión en intento %d para user_id=%s",
                attempt + 1,
                user.pk,
            )

        if candidate is None:
            raise TokenCollisionError(
                f"No se pudo generar un token único tras {self.MAX_RETRIES} intentos "
                f"para el usuario {user.pk}."
            )

        expires_at = timezone.now() + timedelta(hours=self.TOKEN_EXPIRY_HOURS)

        # update_or_create evita el duplicate key del OneToOneField
        invitation_token, _ = InvitationToken.objects.update_or_create(
            user=user,
            defaults={
                'token': candidate,
                'expires_at': expires_at,
                'status': 'active',
            },
        )
        return invitation_token

    # ------------------------------------------------------------------
    # Validación
    # ------------------------------------------------------------------

    def validate_token(self, raw_token: str) -> InvitationToken:
        """
        Valida un token recibido como string.

        Lanza:
          - TokenNotFound    → el token no existe en el Token_Store.
          - TokenExpired     → el token existe pero su expires_at ha pasado.
          - TokenAlreadyUsed → el token tiene status='used'.

        Retorna el InvitationToken si es válido y activo.

        Validates: Requirements 2.1, 2.2
        """
        # Paso 1 – Buscar por valor exacto del token.
        try:
            token_obj = InvitationToken.objects.get(token=raw_token)
        except InvitationToken.DoesNotExist:
            raise TokenNotFound(f"Token no encontrado: {raw_token!r}")

        # Paso 2 – Verificar expiración.
        if token_obj.expires_at <= timezone.now():
            raise TokenExpired(
                f"El token del usuario {token_obj.user_id} ha expirado "
                f"(expires_at={token_obj.expires_at})."
            )

        # Paso 3 – Verificar si ya fue usado.
        if token_obj.status == 'used':
            raise TokenAlreadyUsed(
                f"El token del usuario {token_obj.user_id} ya fue consumido."
            )

        return token_obj

    # ------------------------------------------------------------------
    # Consumo
    # ------------------------------------------------------------------

    def consume_token(self, token: InvitationToken) -> None:
        """
        Marca el token como 'used' y persiste el cambio.

        Validates: Requirements 2.3
        """
        token.status = 'used'
        token.save(update_fields=['status'])


# ---------------------------------------------------------------------------
# LinkBuilder
# ---------------------------------------------------------------------------

class LinkBuilder:
    """Construye el Invitation_Link a partir de la URL base y el token."""

    def build(self, token_value: str) -> str:
        """
        Lee BASE_REGISTRATION_URL de settings.
        Valida que comience con 'https://'.
        Retorna: {base_url}/complete-registration?token={url_encoded_token}

        Lanza ConfigurationError si la URL base es inválida o el token está vacío.

        Validates: Requirements 4.1, 4.2, 4.3, 4.4
        """
        if not token_value:
            raise ConfigurationError("El valor del token está vacío; no se puede construir el enlace.")

        base_url = getattr(settings, 'BASE_REGISTRATION_URL', '')
        # En DEBUG se permite http:// (localhost), en producción se exige https://
        is_valid = base_url.startswith('https://') or (settings.DEBUG and base_url.startswith('http://'))
        if not base_url or not is_valid:
            raise ConfigurationError(
                f"BASE_REGISTRATION_URL debe comenzar con 'https://'. "
                f"Valor actual: {base_url!r}"
            )

        # Eliminar barra final si existe.
        base_url = base_url.rstrip('/')

        query_string = urlencode({'token': token_value})
        return f"{base_url}/complete-registration?{query_string}"


# ---------------------------------------------------------------------------
# PowerAutomateInvitationService
# ---------------------------------------------------------------------------

class PowerAutomateInvitationService:
    """Despacha la invitación al webhook de Power Automate."""

    def dispatch(self, email: str, username: str, invitation_link: str) -> None:
        """
        Envía el payload al webhook configurado en settings.POWER_AUTOMATE_WEBHOOK_URL.
        Incluye opcionalmente el sender configurado en settings.INVITATION_SENDER_EMAIL.

        Valida que los parámetros de entrada (email, username, invitation_link) no estén vacíos.
        Lanza PowerAutomateDispatchError si algún parámetro es inválido o la llamada HTTP falla.

        Validates: Requirements 3.1, 3.6, 3.7, 3.8
        """
        # Requirement 3.8: Validar parámetros de entrada antes de intentar el despacho.
        if not email or not username or not invitation_link:
            raise PowerAutomateDispatchError(
                "Parámetros de invitación inválidos: email, username e invitation_link son requeridos."
            )

        webhook_url = getattr(settings, 'POWER_AUTOMATE_WEBHOOK_URL', '')
        if not webhook_url:
            raise PowerAutomateDispatchError(
                "POWER_AUTOMATE_WEBHOOK_URL no está configurado en settings."
            )

        payload = {
            'tipo': 'invitation',
            'email': email,
            'username': username,
            'invitation_link': invitation_link,
        }

        sender_email = getattr(settings, 'INVITATION_SENDER_EMAIL', None)
        if sender_email:
            payload['sender_email'] = sender_email

        try:
            response = requests.post(webhook_url, json=payload, timeout=30)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise PowerAutomateDispatchError(
                f"Error al llamar al webhook de Power Automate: {exc}"
            ) from exc


# ---------------------------------------------------------------------------
# InvitationService  (orquestador)
# ---------------------------------------------------------------------------

class InvitationService:
    """Orquesta el flujo completo de creación y reenvío de invitaciones."""

    def __init__(self):
        self.token_service = TokenService()
        self.link_builder = LinkBuilder()

    def create_and_invite(self, email: str, username: str, invited_by: User) -> User:
        """
        Crea el usuario en estado pending, genera el token y dispara el correo.
        Lanza excepciones tipadas en caso de error.

        Validates: Requirements 1.1, 1.6, 3.1
        """
        from django.contrib.auth import get_user_model as _get_user_model
        from .exceptions import UserAlreadyExists

        _User = _get_user_model()

        if _User.objects.filter(email=email).exists():
            raise UserAlreadyExists(f"El email '{email}' ya está registrado.")
        if _User.objects.filter(username=username).exists():
            raise UserAlreadyExists(f"El username '{username}' ya está en uso.")

        user = _User.objects.create_user(
            username=username,
            email=email,
            is_active=False,
            password=None,
        )

        invitation_token = self.token_service.generate_token(user)
        invitation_link = self.link_builder.build(invitation_token.token)

        # Delegar el despacho a la tarea Celery para no bloquear la respuesta al admin.
        from .tasks import dispatch_invitation_email
        dispatch_invitation_email.delay(user.pk, invitation_link)

        return user

    def resend(self, user: User, requested_by: User) -> None:
        """
        Invalida el token activo existente, genera uno nuevo y dispara el correo.
        Solo válido para usuarios en estado pending (is_active=False).

        Lanza InvalidResendTarget si el usuario no está en estado pending.

        Validates: Requirements 7.1, 7.2, 7.3, 7.4
        """
        # Verificar que el usuario esté en estado pending.
        perfil = getattr(user, 'perfil', None)
        invitation_status = getattr(perfil, 'invitation_status', None) if perfil else None

        # Fallback: si no hay perfil, usar is_active como indicador.
        if invitation_status is not None:
            if invitation_status != 'pending':
                raise InvalidResendTarget(
                    f"El usuario '{user.username}' tiene estado '{invitation_status}' "
                    f"y no admite reenvío de invitación."
                )
        elif user.is_active:
            raise InvalidResendTarget(
                f"El usuario '{user.username}' ya está activo y no admite reenvío."
            )

        invitation_token = self.token_service.generate_token(user)
        invitation_link = self.link_builder.build(invitation_token.token)

        # Delegar el despacho a la tarea Celery (con reintentos y on_failure) para
        # no bloquear la respuesta al admin y garantizar el manejo de fallos.
        from .tasks import dispatch_invitation_email
        dispatch_invitation_email.delay(user.pk, invitation_link)
