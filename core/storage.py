import os
from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage

class MinIOStorage(S3Boto3Storage):
    """
    Clase de almacenamiento personalizada para forzar el uso de MinIO/S3
    independientemente del STORAGE default (util para Planos y otros archivos criticos).
    """
    def __init__(self, *args, **kwargs):
        # Asegurar que tome las credenciales de MinIO aunque el default sea local
        kwargs.setdefault('access_key', getattr(settings, 'AWS_ACCESS_KEY_ID', None))
        kwargs.setdefault('secret_key', getattr(settings, 'AWS_SECRET_ACCESS_KEY', None))
        kwargs.setdefault('bucket_name', getattr(settings, 'AWS_STORAGE_BUCKET_NAME', None))
        kwargs.setdefault('endpoint_url', getattr(settings, 'AWS_S3_ENDPOINT_URL', None))
        kwargs.setdefault('use_ssl', getattr(settings, 'AWS_S3_USE_SSL', True))
        kwargs.setdefault('verify', getattr(settings, 'AWS_S3_VERIFY', False))
        super().__init__(*args, **kwargs)
