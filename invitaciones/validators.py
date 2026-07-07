"""
Funciones de validación para el módulo de invitaciones.

Valida formato de email (RFC 5322) y formato de username según las
restricciones del sistema de invitaciones.
"""

import re

from django.core.exceptions import ValidationError
from django.core.validators import validate_email as django_validate_email

# Regex para username: letras, números, guiones y guiones bajos, 1–50 caracteres.
_USERNAME_REGEX = re.compile(r"^[A-Za-z0-9_-]{1,50}$")


def validate_email_format(email: str) -> None:
    """
    Valida que *email* tenga formato RFC 5322 usando el validador de Django.

    Raises:
        django.core.exceptions.ValidationError: si el formato es inválido.
    """
    try:
        django_validate_email(email)
    except ValidationError:
        raise ValidationError(
            f"El correo electrónico '{email}' no tiene un formato válido (RFC 5322). "
            "Por favor ingresa una dirección de correo válida, por ejemplo: usuario@dominio.com"
        )


def validate_username_format(username: str) -> None:
    """
    Valida que *username* cumpla con el formato permitido:
    - Solo letras (a-z, A-Z), números (0-9), guiones bajos (_) y guiones (-).
    - Longitud entre 1 y 50 caracteres.

    Raises:
        django.core.exceptions.ValidationError: si el formato no es válido.
    """
    if not _USERNAME_REGEX.match(username):
        raise ValidationError(
            f"El nombre de usuario '{username}' no es válido. "
            "El nombre de usuario debe tener entre 1 y 50 caracteres y solo puede "
            "contener letras (a-z, A-Z), números (0-9), guiones bajos (_) y guiones (-)."
        )
