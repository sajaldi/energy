from django.core.files.storage import default_storage
from django.http import FileResponse, HttpResponseNotFound
import logging

logger = logging.getLogger(__name__)

def media_proxy(request, path):
    """
    Proxy de medios usando el motor de storage de Django.
    Resuelve problemas de Mixed Content (HTTP vs HTTPS) y CORS al cargar modelos 3D y fotos.
    """
    clean_path = path.lstrip('/')
    # Log para ver qué llega exactamente al proxy en producción
    print(f"[DEBUG-PROXY] Request received for: '{path}' -> cleaned to: '{clean_path}'")
    
    try:
        # 1. Verificar si el archivo existe
        if not default_storage.exists(clean_path):
            print(f"[DEBUG-PROXY] 404 - File NOT found in S3/MinIO: '{clean_path}'")
            # Intento de fallback: algunas versiones de django-storages incluyen el bucket o prefijos extra
            return HttpResponseNotFound(f"Archivo '{clean_path}' no encontrado en el storage.")
        
        # 2. Abrir el archivo desde el storage
        file_obj = default_storage.open(clean_path)
        print(f"[DEBUG-PROXY] 200 - Serving file from storage: '{clean_path}'")
        
        # 3. Determinar el Content-Type básico para evitar problemas de descarga
        import mimetypes
        content_type, _ = mimetypes.guess_type(clean_path)
        if not content_type:
             if clean_path.endswith('.glb'): content_type = 'model/gltf-binary'
             elif clean_path.endswith('.gltf'): content_type = 'model/gltf+json'
             else: content_type = 'application/octet-stream'

        # 4. Servir el archivo
        response = FileResponse(file_obj, content_type=content_type)
        
        # CORS obligatorio para que model-viewer pueda cargar el modelo desde el dominio del proxy
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response["Access-Control-Allow-Headers"] = "X-Requested-With, Content-Type"
        
        return response
            
    except Exception as e:
        import traceback
        error_msg = f"Error en media_proxy: {str(e)}"
        print(f"[DEBUG-PROXY] 500 - {error_msg}")
        print(traceback.format_exc())
        return HttpResponseNotFound(error_msg)
