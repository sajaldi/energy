import BAC0
import logging
import asyncio
import threading
from ..models import BACnetGateway, BACnetDevice, BACnetPoint, Telemetry
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)

class BACnetService:
    _instance = None
    _lock = threading.Lock()
    
    def __init__(self):
        self.bacnet = None
        self.ip_local = "10.21.1.138/24"
        self.bbmd_ip = "10.40.193.100"
        self.connected = False

    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def connect(self, force=False):
        if force:
            self.disconnect()

        if not self.connected or self.bacnet is None:
            try:
                import BAC0
                logger.info(f"Iniciando conexión BACnet en {self.ip_local}...")
                self.bacnet = BAC0.lite(ip=self.ip_local, bbmdAddress=self.bbmd_ip, bbmdTTL=60)
                self.connected = True
                logger.info("Servicio BACnet listo.")
            except Exception as e:
                if "already used by BAC0" in str(e):
                    logger.warning("BAC0 ya está inicializado en esta IP. Intentando recuperar instancia activa...")
                    import gc
                    for obj in gc.get_objects():
                        # Buscamos cualquier objeto que parezca una instancia de BAC0 lite
                        if hasattr(obj, 'ip_address') and obj.ip_address == self.ip_local.split('/')[0]:
                            self.bacnet = obj
                            self.connected = True
                            logger.info("Instancia de BAC0 recuperada exitosamente.")
                            return True
                
                logger.error(f"Error al conectar BACnet: {e}")
                self.disconnect() 
                return False
        return self.connected

    async def read_point(self, address):
        """Lee un punto de forma asincrona para no bloquear el hilo de Django"""
        if not self.connect():
            raise Exception("No se pudo establecer conexion BACnet")
        
        try:
            # Envolviendo la lectura en un timeout para seguridad
            return await asyncio.wait_for(self.bacnet.read(address), timeout=5.0)
        except (AttributeError, Exception) as e:
            # Si hay un error de tipo 'NoneType' object has no attribute 'append' (transport cerrado)
            # o cualquier fallo de red, desconectamos para forzar una nueva conexión en el próximo intento.
            logger.warning(f"Fallo en lectura BACnet: {e}. Forzando desconexión para reintento.")
            self.disconnect()
            raise e

    def disconnect(self):
        if self.bacnet:
            try:
                self.bacnet.disconnect()
            except Exception as e:
                logger.debug(f"Error al desconectar BACnet (ignorable): {e}")
            self.bacnet = None
        self.connected = False

    async def discover_device_points(self, device_obj):
        """
        Escanea un dispositivo y registra automáticamente todos sus puntos en la base de datos.
        """
        if not self.connect():
            return False
            
        target_address = device_obj.address
        device_id = device_obj.device_id
        
        try:
            logger.info(f"Iniciando descubrimiento de puntos para {device_obj.name} ({target_address})...")
            
            # Creamos un objeto 'device' de BAC0 vinculado a nuestra instancia lite
            # En la versión asíncrona de BAC0, el constructor de 'device' debe ser esperado (await)
            remote_dev = await BAC0.device(target_address, device_id, self.bacnet, poll=0)
            
            puntos_encontrados = 0
            for obj in remote_dev.points:
                obj_type = obj.properties.address[0]
                instance = obj.properties.address[1]
                
                # Sincronizar con la base de datos (usando sync_to_async para Django models)
                await sync_to_async(BACnetPoint.objects.update_or_create)(
                    device=device_obj,
                    object_type=obj_type,
                    instance=instance,
                    defaults={
                        'name': obj.properties.name,
                        'description': getattr(obj.properties, 'description', ''),
                        'unit': getattr(obj.properties, 'units', '')
                    }
                )
                puntos_encontrados += 1
                
            logger.info(f"Descubrimiento completado: {puntos_encontrados} puntos registrados para {device_obj.name}.")
            return True
            
        except Exception as e:
            logger.error(f"Error descubriendo puntos en {device_obj.name}: {e}")
            return False

# Instancia global accesible desde fuera
bacnet_instance = BACnetService.get_instance()
