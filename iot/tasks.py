from celery import shared_task
from .services.bacnet import BACnetService
from .models import BACnetGateway
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@shared_task(name="iot.tasks.poll_telemetry")
def poll_telemetry():
    """
    Tarea periódica para recolectar datos de todos los gateways activos.
    """
    gateways = BACnetGateway.objects.filter(is_active=True)
    if not gateways.exists():
        return "No hay gateways BACnet activos para procesar."

    for gw in gateways:
        logger.info(f"Iniciando polling para gateway: {gw.nombre}")
        service = BACnetService(gw.id)
        service.poll_all_points()
        # Actualizar fecha de última sincronización
        gw.last_sync = datetime.now() # Necesito importar datetime
        gw.save()
        service.disconnect()
    
    return f"Polling completado para {gateways.count()} gateways."

@shared_task(name="iot.tasks.discover_bacnet_devices")
def discover_bacnet_devices(gateway_id, networks=None):
    """
    Tarea para descubrir nuevos dispositivos en la red.
    """
    try:
        service = BACnetService(gateway_id)
        devices = service.discover_devices(networks=networks)
        service.disconnect()
        return f"Descubrimiento finalizado. {len(devices)} dispositivos encontrados/actualizados."
    except Exception as e:
        return f"Error en descubrimiento: {str(e)}"
