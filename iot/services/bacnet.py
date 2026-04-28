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
        self.ip_local = "10.21.1.132/24"
        self.bbmd_ip = "10.40.193.100"
        self.connected = False

    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def connect(self):
        if not self.connected or self.bacnet is None:
            try:
                logger.info(f"Conectando servicio global BACnet en {self.ip_local} via BBMD {self.bbmd_ip}...")
                self.bacnet = BAC0.lite(ip=self.ip_local, bbmdAddress=self.bbmd_ip, bbmdTTL=60)
                self.connected = True
                logger.info("Servicio BACnet conectado exitosamente.")
            except Exception as e:
                logger.error(f"Error al conectar BACnet: {e}")
                self.connected = False
        return self.connected

    async def read_point(self, address):
        """Lee un punto de forma asincrona para no bloquear el hilo de Django"""
        if not self.connect():
            raise Exception("No se pudo establecer conexion BACnet")
        
        # Envolviendo la lectura en un timeout para seguridad
        return await asyncio.wait_for(self.bacnet.read(address), timeout=5.0)

    def disconnect(self):
        if self.bacnet:
            try:
                self.bacnet.disconnect()
            except:
                pass
            self.bacnet = None
            self.connected = False

# Instancia global accesible desde fuera
bacnet_instance = BACnetService.get_instance()
