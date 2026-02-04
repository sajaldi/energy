"""
Script de prueba para verificar la conexión a MinIO
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

try:
    # Test 1: Verificar configuración
    print(f"[INFO] Storage Backend: {default_storage.__class__.__name__}")
    print(f"[INFO] Bucket: {default_storage.bucket_name}")
    print(f"[INFO] Endpoint: {default_storage.endpoint_url}")
    
    # Test 2: Intentar listar archivos
    print("\n[INFO] Intentando listar archivos en MinIO...")
    files = default_storage.listdir('modelos_fotos/')
    print(f"[SUCCESS] Conexión exitosa. Archivos encontrados: {len(files[1])}")
    
    # Test 3: Subir archivo de prueba
    print("\n[INFO] Subiendo archivo de prueba...")
    test_content = ContentFile(b"Test MinIO Connection")
    test_path = default_storage.save('test_minio_connection.txt', test_content)
    print(f"[SUCCESS] Archivo subido: {test_path}")
    
    # Test 4: Obtener URL
    url = default_storage.url(test_path)
    print(f"[SUCCESS] URL generada: {url}")
    
    # Test 5: Eliminar archivo de prueba
    default_storage.delete(test_path)
    print(f"[SUCCESS] Archivo de prueba eliminado")
    
    print("\n✅ TODAS LAS PRUEBAS PASARON - MinIO está configurado correctamente")
    
except Exception as e:
    print(f"\n❌ ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
