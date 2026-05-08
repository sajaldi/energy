import logging
from django.db import models
from .powerautomate_utils import send_to_power_automate
from .dynamics_registry import SYNC_CONFIG

logger = logging.getLogger(__name__)

def get_entity_metadata(model_class):
    """Obtiene la configuración de sincronización para un modelo."""
    model_name = f"{model_class._meta.app_label}.{model_class._meta.object_name}"
    return SYNC_CONFIG.get(model_name)

def sync_instance_to_dynamics(instance):
    """
    Sincroniza una instancia de modelo de Django enviando los datos a Power Automate.
    Power Automate se encargará de crear o actualizar el registro en Dynamics.
    """
    config = get_entity_metadata(instance.__class__)
    if not config:
        return None

    entity_name = config['entity']
    fields_to_sync = config['fields']
    mapping = config.get('mapping', {})

    # Construir data
    data = {}
    for field in fields_to_sync:
        val = getattr(instance, field)
        
        # Mapear nombre de campo si existe en el mapping
        d365_field = mapping.get(field, field)
        
        # Conversión básica
        if hasattr(val, 'isoformat'): # Datetime
            data[d365_field] = val.isoformat()
        elif isinstance(val, (int, float, str, bool)) or val is None:
            data[d365_field] = val
        else:
            data[d365_field] = str(val)

    # Payload para Power Automate
    payload = {
        'entity': entity_name,
        'action': 'UPSERT',
        'dynamics_guid': getattr(instance, 'dynamics_guid', None),
        'django_id': instance.pk,
        'data': data
    }

    logger.info(f"Enviando {instance} a Power Automate para respaldo en {entity_name}")
    return send_to_power_automate(payload)
