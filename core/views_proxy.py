from django.core.files.storage import default_storage
from django.http import FileResponse, HttpResponseNotFound
import logging

logger = logging.getLogger(__name__)

def media_proxy(request, path):
    """
    Proxy de medios usando el motor de storage de Django.
    """
    clean_path = path.lstrip('/')
    print(f"[DEBUG-PROXY] Request for path: {clean_path}")
    
    try:
        # Verificamos si el archivo existe usando el driver oficial de S3/MinIO
        if not default_storage.exists(clean_path):
            print(f"[DEBUG-PROXY] 404 - File NOT found in storage: {clean_path}")
            return HttpResponseNotFound("Archivo no encontrado en el servidor de almacenamiento.")
        
        # Abrimos el archivo. Boto3 se encarga de la autenticación automáticamente.
        file_obj = default_storage.open(clean_path)
        print(f"[DEBUG-PROXY] 200 - Serving file: {clean_path}")
        
        # Servimos el archivo directamente al navegador
        response = FileResponse(file_obj)
        # Aseguramos CORS permissive para el proxy mismo por si acaso
        response["Access-Control-Allow-Origin"] = "*"
        return response
            
    except Exception as e:
        print(f"[DEBUG-PROXY] 500 - Error accessing file: {str(e)}")
        return HttpResponseNotFound(f"Error al acceder al archivo: {str(e)}")
