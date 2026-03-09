from django.core.files.storage import default_storage
from django.http import FileResponse, HttpResponseNotFound
import logging

logger = logging.getLogger(__name__)

def media_proxy(request, path):
    """
    Proxy de medios usando el motor de storage de Django.
    Usa automáticamente las credenciales de MinIO (boto3)
    para saltarse el error 403 Forbidden.
    """
    clean_path = path.lstrip('/')
    
    try:
        # Verificamos si el archivo existe usando el driver oficial de S3/MinIO
        if not default_storage.exists(clean_path):
            logger.warning(f"Archivo no encontrado en MinIO: {clean_path}")
            return HttpResponseNotFound("Archivo no encontrado en el servidor de almacenamiento.")
        
        # Abrimos el archivo. Boto3 se encarga de la autenticación automáticamente.
        file_obj = default_storage.open(clean_path)
        
        # Servimos el archivo directamente al navegador
        return FileResponse(file_obj)
            
    except Exception as e:
        logger.error(f"Error fatal en MinIO Proxy: {str(e)}")
        return HttpResponseNotFound(f"Error al acceder al archivo: {str(e)}")
