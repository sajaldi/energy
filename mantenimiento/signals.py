from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.utils import timezone
from .models import OrdenTrabajo, CierreOrdenTrabajo, Aviso
from activos.models import Activo, DowntimeActivo

@receiver(post_save, sender=Aviso)
def handle_aviso_status_and_downtime(sender, instance, created, **kwargs):
    """
    Maneja el inicio y fin de paradas desde los Avisos de Mantenimiento.
    """
    if not instance.activo:
        return
        
    activo = instance.activo
    
    if instance.equipo_parado and instance.estado in ['ABIERTO', 'PROCESO']:
        DowntimeActivo.objects.get_or_create(
            activo=activo,
            aviso=instance,
            fin__isnull=True,
            defaults={
                'inicio': instance.fecha_inicio_parada or instance.creado_en or timezone.now(), 
                'motivo': f"Aviso AV-{instance.id}: {instance.get_tipo_display()}"
            }
        )
    else:
        # Si se cierra, cancela o se quita la marca de equipo parado
        downtimes = DowntimeActivo.objects.filter(activo=activo, aviso=instance, fin__isnull=True)
        if downtimes.exists():
            fin_time = instance.fecha_fin_parada or instance.fecha_cierre or timezone.now()
            downtimes.update(fin=fin_time)
            for d in DowntimeActivo.objects.filter(activo=activo, aviso=instance, duracion_horas=0):
                d.save()
                
    activo.actualizar_estado(save=True)

@receiver(post_save, sender=OrdenTrabajo)
def handle_ot_status_and_downtime(sender, instance, created, **kwargs):
    """
    Sincroniza el estado de los activos y maneja el historial de paradas
    cuando se guarda una Orden de Trabajo.
    """
    for activo in instance.activos.all():
        # Manejar Historial de Parada
        if instance.equipo_parado and instance.estado not in ['REALIZADA', 'CANCELADA']:
            # Si hay un aviso asociado, enlazar el downtime existente
            dt = None
            if instance.aviso:
                dt = DowntimeActivo.objects.filter(activo=activo, aviso=instance.aviso, fin__isnull=True).first()
                if dt and not dt.orden_trabajo:
                    dt.orden_trabajo = instance
                    dt.save()
            
            if not dt:
                defaults = {'inicio': timezone.now(), 'motivo': f"OT {instance.codigo_de_orden or instance.id}"}
                if instance.aviso: defaults['aviso'] = instance.aviso
                
                DowntimeActivo.objects.get_or_create(
                    activo=activo,
                    orden_trabajo=instance,
                    fin__isnull=True,
                    defaults=defaults
                )
        else:
            # Si ya no está parado o la OT se cerró, cerrar el registro de downtime
            DowntimeActivo.objects.filter(
                activo=activo,
                orden_trabajo=instance,
                fin__isnull=True
            ).update(fin=timezone.now())
            for downtime in DowntimeActivo.objects.filter(activo=activo, orden_trabajo=instance, fin__isnull=False, duracion_horas=0):
                downtime.save()
                
        activo.actualizar_estado(save=True)

@receiver(m2m_changed, sender=OrdenTrabajo.activos.through)
def handle_ot_activos_changed(sender, instance, action, pk_set, **kwargs):
    """
    Maneja cambios en la relación M2M de activos en una OT.
    """
    if action in ["post_add", "post_remove", "post_clear"]:
        if pk_set:
            activos = Activo.objects.filter(pk__in=pk_set)
        else:
            activos = instance.activos.all()
            
        for activo in activos:
            if action == "post_add" and instance.equipo_parado and instance.estado not in ['REALIZADA', 'CANCELADA']:
                dt = None
                if instance.aviso:
                    dt = DowntimeActivo.objects.filter(activo=activo, aviso=instance.aviso, fin__isnull=True).first()
                    if dt and not dt.orden_trabajo:
                        dt.orden_trabajo = instance
                        dt.save()
                if not dt:
                    defaults = {'inicio': timezone.now(), 'motivo': f"OT {instance.codigo_de_orden or instance.id}"}
                    if instance.aviso: defaults['aviso'] = instance.aviso
                    DowntimeActivo.objects.get_or_create(
                        activo=activo,
                        orden_trabajo=instance,
                        fin__isnull=True,
                        defaults=defaults
                    )
            elif action == "post_remove":
                DowntimeActivo.objects.filter(
                    activo=activo,
                    orden_trabajo=instance,
                    fin__isnull=True
                ).update(fin=timezone.now())
                for d in DowntimeActivo.objects.filter(activo=activo, orden_trabajo=instance, fin__isnull=False, duracion_horas=0):
                    d.save()
                    
            activo.actualizar_estado(save=True)

@receiver(post_save, sender=CierreOrdenTrabajo)
def handle_cierre_ot_status(sender, instance, **kwargs):
    """
    Al cerrar una OT, asegurar que los activos vuelvan a su estado operativo
    y se cierren los registros de downtime asociados (y avisos si los hay).
    """
    ot = instance.orden_trabajo
    for activo in ot.activos.all():
        DowntimeActivo.objects.filter(
            activo=activo,
            orden_trabajo=ot,
            fin__isnull=True
        ).update(fin=instance.fecha_fin_real)
        
        for d in DowntimeActivo.objects.filter(activo=activo, orden_trabajo=ot, duracion_horas=0):
            d.save()
            
        activo.actualizar_estado(save=True)
    
    # Cerrar el Aviso asociado si existe y marcar fin de parada
    if ot.aviso and ot.aviso.estado != 'CERRADO':
        ot.aviso.estado = 'CERRADO'
        ot.aviso.fecha_cierre = instance.fecha_fin_real
        if ot.aviso.equipo_parado and not ot.aviso.fecha_fin_parada:
            ot.aviso.fecha_fin_parada = instance.fecha_fin_real
        ot.aviso.save()

    # Reprogramación dinámica de órdenes futuras para Rutinas
    if ot.programacion and ot.rutina:
        try:
            ot.programacion.reprogramar_futuras_ordenes(ot, instance.fecha_fin_real)
        except Exception as e:
            # Podríamos loguear esto, por ahora print para debug
            print(f"Error al reprogramar órdenes futuras para OT #{ot.id}: {e}")

