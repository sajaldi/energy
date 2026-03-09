import os
import datetime as real_datetime
import botocore.auth
from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage

# --- BOTOCORE CLOCK SKEW MONKEYPATCH ---
# Solución al error "403 Forbidden" (RequestTimeTooSkewed) causado porque
# el reloj de la VM local tiene un gran desfase con el servidor remoto MinIO.
class _MockDatetime:
    @classmethod
    def utcnow(cls):
        return real_datetime.datetime.utcnow() + real_datetime.timedelta(hours=7, minutes=5)
    
    @classmethod
    def strptime(cls, *args, **kwargs):
        return real_datetime.datetime.strptime(*args, **kwargs)

class _MockDatetimeModule:
    datetime = _MockDatetime
    timedelta = real_datetime.timedelta
    tzinfo = real_datetime.tzinfo

botocore.auth.datetime = _MockDatetimeModule()
# ---------------------------------------

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
