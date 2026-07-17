from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from .models import ExpedienteMensual
from notificaciones.utils import crear_notificacion


@receiver(pre_save, sender=ExpedienteMensual)
def capture_old_expediente_status(sender, instance, **kwargs):
    try:
        if instance.pk:
            instance._old_status = ExpedienteMensual.objects.get(pk=instance.pk).estado
        else:
            instance._old_status = None
    except ExpedienteMensual.DoesNotExist:
        instance._old_status = None


@receiver(post_save, sender=ExpedienteMensual)
def handle_expediente_notifications(sender, instance, created, **kwargs):
    old = getattr(instance, '_old_status', None)
    if not old or old == instance.estado:
        return

    perfil = instance.empresa.usuarios_portal.filter(activo=True).first()
    user = perfil.user if perfil else None
    if not user:
        return

    url = f"/portalsub/expediente/{instance.mes}/{instance.anio}/"

    if old in ('ENVIADO', 'EN_REVISION') and instance.estado == 'APROBADO':
        crear_notificacion(
            user=user,
            titulo="Expediente Aprobado",
            mensaje=f"Tu expediente de {instance.mes}/{instance.anio} ha sido aprobado.",
            tipo='SUCCESS',
            modulo='PORTAL_SUB',
            enlace=url,
            icono='checkmark-circle-outline',
        )
    elif old in ('ENVIADO', 'EN_REVISION') and instance.estado == 'RECHAZADO':
        crear_notificacion(
            user=user,
            titulo="Expediente Rechazado",
            mensaje=f"Tu expediente de {instance.mes}/{instance.anio} ha sido rechazado. Revisa las observaciones.",
            tipo='ERROR',
            modulo='PORTAL_SUB',
            enlace=url,
            icono='close-circle-outline',
        )
