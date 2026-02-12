from django.http import StreamingHttpResponse, HttpResponseNotFound
import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def media_proxy(request, path):
    """
    Actúa como un puente entre el navegador y MinIO.
    Resuelve el problema de Mixed Content y Proxies externos.
    """
    # Construimos la URL interna de MinIO
    # Usamos la IP pública y puerto que sabemos que funciona
    minio_url = f"http://181.115.47.107:9000/energia-media/{path}"
    
    try:
        # Django descarga el archivo de MinIO (Comunicación Backend-Backend)
        response = requests.get(minio_url, stream=True, timeout=10)
        
        if response.status_code == 200:
            # Se lo entregamos al navegador con el mismo tipo de contenido
            django_response = StreamingHttpResponse(
                response.iter_content(chunk_size=8192),
                content_type=response.headers.get('Content-Type')
            )
            django_response['Content-Disposition'] = response.headers.get('Content-Disposition', 'inline')
            return django_response
        else:
            logger.error(f"Error en MinIO Proxy: {response.status_code} para {minio_url}")
            return HttpResponseNotFound("Archivo no encontrado en el servidor de archivos.")
            
    except Exception as e:
        logger.error(f"Error fatal en MinIO Proxy: {str(e)}")
        return HttpResponseNotFound("Error al conectar con el servidor de archivos.")
