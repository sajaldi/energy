import BAC0
import logging
from datetime import datetime
from ..models import BACnetGateway, BACnetDevice, BACnetPoint, Telemetry

logger = logging.getLogger(__name__)

class BACnetService:
    def __init__(self, gateway_id):
        try:
            self.gateway_db = BACnetGateway.objects.get(id=gateway_id)
        except BACnetGateway.DoesNotExist:
            logger.error(f"Gateway con ID {gateway_id} no existe.")
            self.gateway_db = None
        self.bacnet = None
        
    def connect(self):
        if not self.gateway_db:
            return False
        try:
            # Inicializar BAC0
            # BAC0.lite crea una interfaz local para hablar en la red BACnet
            # ip: la IP del servidor en la red VPN
            self.bacnet = BAC0.lite(
                ip=self.gateway_db.ip_address, 
                port=self.gateway_db.port, 
                deviceId=self.gateway_db.device_id
            )
            logger.info(f"Conectado a BACnet via {self.gateway_db.ip_address}")
            return True
        except Exception as e:
            logger.error(f"Error conectando a BACnet: {e}")
            return False

    def discover_devices(self, networks=None):
        """
        Realiza un Who-Is en la red para encontrar controladores de Reliable Controls u otros.
        """
        if not self.bacnet:
            if not self.connect(): return []
            
        logger.info("Iniciando descubrimiento de dispositivos BACnet...")
        # discover() devuelve una lista de dispositivos encontrados
        try:
            discovered = self.bacnet.discover(networks=networks)
        except Exception as e:
            logger.error(f"Error en descubrimiento: {e}")
            return []

        found_devices = []
        for dev in discovered:
            # En BAC0, dev suele ser un objeto con address y device_id
            try:
                addr = getattr(dev, 'address', str(dev))
                dev_id = getattr(dev, 'device_id', None)
                
                if not dev_id: continue

                # Intentar obtener información básica
                name = ""
                vendor = ""
                try:
                    name = self.bacnet.read(f"{addr} device {dev_id} objectName")
                    vendor = self.bacnet.read(f"{addr} device {dev_id} vendorName")
                except:
                    pass
                    
                device_obj, created = BACnetDevice.objects.update_or_create(
                    device_id=dev_id,
                    defaults={
                        'gateway': self.gateway_db,
                        'address': str(addr),
                        'name': str(name) if name else f"Device {dev_id}",
                        'vendor': str(vendor) if vendor else "Unknown",
                        'is_online': True
                    }
                )
                found_devices.append(device_obj)
            except Exception as e:
                logger.warning(f"Error procesando dispositivo descubierto: {e}")
            
        return found_devices

    def poll_all_points(self):
        """
        Lee todos los puntos configurados y guarda la telemetría.
        Ideal para ejecutarse en una tarea de Celery.
        """
        if not self.bacnet:
            if not self.connect(): return
            
        points = BACnetPoint.objects.filter(device__gateway=self.gateway_db)
        
        for pt in points:
            try:
                # Formato: <address> <object_type> <instance> presentValue
                query = f"{pt.device.address} {pt.object_type} {pt.instance} presentValue"
                val = self.bacnet.read(query)
                
                if pt.save_history:
                    Telemetry.objects.create(
                        point=pt,
                        value=float(val),
                        status="OK"
                    )
                
                # Actualizar estado del dispositivo
                if not pt.device.is_online:
                    pt.device.is_online = True
                    pt.device.save()
            except Exception as e:
                logger.warning(f"Error leyendo punto {pt}: {e}")
                # Si falla, marcamos dispositivo como offline temporalmente
                pt.device.is_online = False
                pt.device.save()

    def disconnect(self):
        if self.bacnet:
            try:
                self.bacnet.disconnect()
            except:
                pass
            self.bacnet = None
