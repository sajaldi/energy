from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from .models import Requisicion, OrdenCompra
from notificaciones.utils import crear_notificacion


@receiver(pre_save, sender=Requisicion)
def capture_old_requisicion_status(sender, instance, **kwargs):
    try:
        if instance.pk:
            instance._old_estado = Requisicion.objects.get(pk=instance.pk).estado_requisicion
        else:
            instance._old_estado = None
    except Requisicion.DoesNotExist:
        instance._old_estado = None


@receiver(post_save, sender=Requisicion)
def handle_requisicion_notifications(sender, instance, created, **kwargs):
    req_url = f"/presupuestos/requisiciones/{instance.cr8ca_requisicionid}/pdf/"
    req_codigo = instance.cr8ca_requisicion or str(instance.cr8ca_requisicionid)[:8]
    old = getattr(instance, '_old_estado', None)

    # Nueva requisición pendiente de autorizar
    if created and instance.estado_requisicion == 'PENDIENTE' and instance.aprobador:
        crear_notificacion(
            user=instance.aprobador,
            titulo="Requisición Pendiente de Autorizar",
            mensaje=f"La requisición {req_codigo} está esperando tu autorización.",
            tipo='INFO',
            modulo='PRESUPUESTOS',
            enlace=req_url,
            icono='document-text-outline',
        )

    # Autorizada -> notificar al solicitante
    elif old != 'AUTORIZADO' and instance.estado_requisicion == 'AUTORIZADO' and instance.usuario_solicitante:
        crear_notificacion(
            user=instance.usuario_solicitante,
            titulo="Requisición Autorizada",
            mensaje=f"La requisición {req_codigo} ha sido autorizada.",
            tipo='SUCCESS',
            modulo='PRESUPUESTOS',
            enlace=req_url,
            icono='checkmark-circle-outline',
        )

    # Rechazada -> notificar al solicitante
    elif old != 'RECHAZADO' and instance.estado_requisicion == 'RECHAZADO' and instance.usuario_solicitante:
        crear_notificacion(
            user=instance.usuario_solicitante,
            titulo="Requisición Rechazada",
            mensaje=f"La requisición {req_codigo} ha sido rechazada.",
            tipo='ERROR',
            modulo='PRESUPUESTOS',
            enlace=req_url,
            icono='close-circle-outline',
        )

    # Procesada a OC
    elif old != 'EN_ORDEN_COMPRA' and instance.estado_requisicion == 'EN_ORDEN_COMPRA' and instance.usuario_solicitante:
        crear_notificacion(
            user=instance.usuario_solicitante,
            titulo="Requisición Procesada a OC",
            mensaje=f"La requisición {req_codigo} ha sido procesada a Orden de Compra.",
            tipo='SUCCESS',
            modulo='PRESUPUESTOS',
            enlace=req_url,
            icono='receipt-outline',
        )


@receiver(pre_save, sender=OrdenCompra)
def capture_old_oc_status(sender, instance, **kwargs):
    try:
        if instance.pk:
            instance._old_estado = OrdenCompra.objects.get(pk=instance.pk).estado
        else:
            instance._old_estado = None
    except OrdenCompra.DoesNotExist:
        instance._old_estado = None


@receiver(post_save, sender=OrdenCompra)
def handle_oc_notifications(sender, instance, created, **kwargs):
    oc_url = f"/presupuestos/ordenes-compra/{instance.id}/detalle/"
    old = getattr(instance, '_old_estado', None)

    # OC creada
    if created:
        if instance.requisicion and instance.requisicion.usuario_solicitante:
            crear_notificacion(
                user=instance.requisicion.usuario_solicitante,
                titulo="Orden de Compra Generada",
                mensaje=f"La OC {instance.numero_oc} ha sido generada.",
                tipo='SUCCESS',
                modulo='PRESUPUESTOS',
                enlace=oc_url,
                icono='receipt-outline',
            )

    # OC confirmada
    if old != 'CONFIRMADA' and instance.estado == 'CONFIRMADA' and instance.creado_por:
        crear_notificacion(
            user=instance.creado_por,
            titulo="OC Confirmada",
            mensaje=f"La OC {instance.numero_oc} ha sido confirmada por el proveedor.",
            tipo='SUCCESS',
            modulo='PRESUPUESTOS',
            enlace=oc_url,
            icono='checkmark-circle-outline',
        )

    # OC recibida
    if old != 'RECIBIDA' and instance.estado == 'RECIBIDA' and instance.creado_por:
        crear_notificacion(
            user=instance.creado_por,
            titulo="OC Recibida",
            mensaje=f"La OC {instance.numero_oc} ha sido marcada como recibida.",
            tipo='SUCCESS',
            modulo='PRESUPUESTOS',
            enlace=oc_url,
            icono='archive-outline',
        )

    # OC cancelada
    if old != 'CANCELADA' and instance.estado == 'CANCELADA':
        if instance.creado_por:
            crear_notificacion(
                user=instance.creado_por,
                titulo="OC Cancelada",
                mensaje=f"La OC {instance.numero_oc} ha sido cancelada.",
                tipo='WARNING',
                modulo='PRESUPUESTOS',
                enlace=oc_url,
                icono='close-outline',
            )
        if instance.requisicion and instance.requisicion.usuario_solicitante:
            crear_notificacion(
                user=instance.requisicion.usuario_solicitante,
                titulo="OC Cancelada",
                mensaje=f"La OC {instance.numero_oc} asociada a tu requisición ha sido cancelada.",
                tipo='WARNING',
                modulo='PRESUPUESTOS',
                enlace=oc_url,
                icono='close-outline',
            )
