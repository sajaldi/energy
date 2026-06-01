import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .dynamics_registry import SYNC_CONFIG
from .tasks import task_sync_to_dynamics
from kombu.exceptions import OperationalError

logger = logging.getLogger(__name__)

def handle_dynamics_sync(sender, instance, created, **kwargs):
    """
    Signal handler genérico para encolar la sincronización a Dynamics.
    """
    app_label = sender._meta.app_label
    model_name = sender._meta.object_name
    full_name = f"{app_label}.{model_name}"
    
    if full_name in SYNC_CONFIG:
        # Encolar tarea de Celery
        # Usamos transaction.on_commit si queremos asegurar que el registro local se guardó bien
        from django.db import transaction
        
        def call_sync():
            try:
                logger.info(f"Encolando sincronización para {full_name} ID: {instance.pk}")
                task_sync_to_dynamics.delay(app_label, model_name, instance.pk)
            except OperationalError as e:
                logger.warning(f"No se pudo encolar sync a Dynamics (broker no disponible): {e}")
            except Exception as e:
                logger.error(f"Error al encolar sync a Dynamics: {e}")
        
        transaction.on_commit(call_sync)

def register_dynamics_signals():
    """
    Registra dinámicamente las señales para todos los modelos en SYNC_CONFIG.
    """
    from django.apps import apps
    
    for full_name in SYNC_CONFIG:
        try:
            model = apps.get_model(full_name)
            post_save.connect(handle_dynamics_sync, sender=model, dispatch_uid=f"dynamics_sync_{full_name}")
            logger.info(f"Señal de Dynamics registrada para {full_name}")
        except Exception as e:
            logger.error(f"No se pudo registrar señal para {full_name}: {e}")
