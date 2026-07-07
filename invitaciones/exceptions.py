"""
Jerarquía de excepciones tipadas para el módulo de invitaciones.
"""


class InvitationError(Exception):
    """Base para todos los errores del flujo de invitación."""


class TokenNotFound(InvitationError):
    """El token no existe en el Token_Store."""


class TokenExpired(InvitationError):
    """El token existe pero su expires_at ha pasado."""


class TokenAlreadyUsed(InvitationError):
    """El token ya fue consumido."""


class TokenCollisionError(InvitationError):
    """No se pudo generar un token único tras MAX_RETRIES intentos."""


class ConfigurationError(InvitationError):
    """La configuración del sistema es inválida (p.ej. base URL sin HTTPS)."""


class PowerAutomateDispatchError(InvitationError):
    """El flujo de Power Automate falló tras todos los reintentos."""


class UserAlreadyExists(InvitationError):
    """El email o username ya están registrados en el sistema."""


class InvalidResendTarget(InvitationError):
    """El usuario no está en estado pending y no admite reenvío."""
