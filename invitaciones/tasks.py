"""
Tareas Celery del módulo de invitaciones.

Tareas:
  - dispatch_invitation_email : despacha el correo de invitación vía Power Automate.
  - cleanup_expired_tokens    : elimina tokens expirados no usados del Token_Store.
"""

import logging
from datetime import datetime

from celery import Task, shared_task
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def notify_admin_of_failure(user_id: int, error: Exception) -> None:
    """
    Notifica al administrador del sistema sobre un fallo definitivo
    en el despacho del correo de invitación.

    Emite un log CRITICAL y, si hay ADMINS configurados en settings,
    envía un email usando mail_admins de Django.
    """
    from django.core.mail import mail_admins

    subject = f"[Invitaciones] Fallo definitivo al enviar correo — user_id={user_id}"
    message = (
        f"El correo de invitación para el usuario con id={user_id} "
        f"no pudo enviarse tras todos los reintentos.\n\n"
        f"Error: {error}\n"
        f"Timestamp: {datetime.utcnow().isoformat()}Z"
    )

    logger.critical(
        "notify_admin_of_failure | user_id=%s | error=%s | timestamp=%s",
        user_id,
        error,
        datetime.utcnow().isoformat(),
    )

    try:
        mail_admins(subject=subject, message=message, fail_silently=True)
    except Exception as mail_exc:  # pragma: no cover
        logger.error(
            "notify_admin_of_failure: no se pudo enviar email al admin | %s",
            mail_exc,
        )


# ---------------------------------------------------------------------------
# Clase base para on_failure
# ---------------------------------------------------------------------------

class InvitationEmailTask(Task):
    """
    Clase base de la tarea de despacho que implementa el callback on_failure.

    Cuando todos los reintentos se agotan, on_failure loguea el error con
    user_id, detalles del error y timestamp, y llama a notify_admin_of_failure.
    """

    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """
        Callback invocado cuando la tarea falla tras agotar todos los reintentos.
        """
        user_id = args[0] if args else kwargs.get('user_id', 'unknown')

        logger.error(
            "dispatch_invitation_email.on_failure | user_id=%s | task_id=%s "
            "| error=%s | timestamp=%s",
            user_id,
            task_id,
            exc,
            datetime.utcnow().isoformat(),
        )

        notify_admin_of_failure(user_id, exc)

        super().on_failure(exc, task_id, args, kwargs, einfo)


# ---------------------------------------------------------------------------
# Tarea principal de despacho
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    base=InvitationEmailTask,
    max_retries=3,
    name='invitaciones.tasks.dispatch_invitation_email',
)
def dispatch_invitation_email(self, user_id: int, invitation_link: str):
    """
    Despacha el correo de invitación al webhook de Power Automate.

    Reintenta hasta 3 veces con un intervalo de 60 segundos entre intentos.
    En caso de fallo definitivo (último reintento agotado), el callback
    ``on_failure`` notifica al administrador del sistema.

    Validates: Requirements 3.6
    """
    try:
        from .services import PowerAutomateInvitationService

        User = get_user_model()
        user = User.objects.get(pk=user_id)

        PowerAutomateInvitationService().dispatch(
            email=user.email,
            username=user.username,
            invitation_link=invitation_link,
        )

        logger.info(
            "dispatch_invitation_email: correo despachado exitosamente | user_id=%s",
            user_id,
        )

    except Exception as exc:
        logger.error(
            "dispatch_invitation_email: PA dispatch failed | user_id=%s | error=%s",
            user_id,
            exc,
        )
        raise self.retry(exc=exc, countdown=60)


# ---------------------------------------------------------------------------
# Tarea de limpieza periódica
# ---------------------------------------------------------------------------

@shared_task(name='invitaciones.tasks.cleanup_expired_tokens')
def cleanup_expired_tokens():
    """
    Elimina del Token_Store todos los InvitationToken cuyo ``expires_at``
    haya pasado y cuyo ``status`` sea distinto de 'used'.

    Programada para ejecutarse cada 6 horas via Celery Beat.

    Validates: Requirements 8.1, 8.2
    """
    from django.utils import timezone
    from .models import InvitationToken

    deleted_count, _ = InvitationToken.objects.filter(
        expires_at__lt=timezone.now()
    ).exclude(status='used').delete()

    logger.info(
        "cleanup_expired_tokens: %d token(s) expirado(s) eliminado(s).",
        deleted_count,
    )

    return deleted_count
