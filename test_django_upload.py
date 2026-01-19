import os
import django
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

# Configurar el entorno de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

def test_django_upload():
    filename = 'test/django_test_upload.txt'
    content = b'Prueba de carga desde Django Storage a MinIO'
    
    print(f"🚀 Iniciando prueba de carga en Django...")
    print(f"📁 Archivo: {filename}")
    
    try:
        # 1. Guardar archivo usando el storage por defecto
        if default_storage.exists(filename):
            print(f"🗑️ El archivo ya existe, eliminándolo...")
            default_storage.delete(filename)
            
        path = default_storage.save(filename, ContentFile(content))
        print(f"✅ Archivo guardado exitosamente en: {path}")
        
        # 2. Generar URL
        url = default_storage.url(path)
        print(f"🔗 URL generada: {url}")
        
        # 3. Intentar leerlo de vuelta
        with default_storage.open(path) as f:
            read_content = f.read()
            if read_content == content:
                print("✅ Verificación de lectura exitosa (contenido coincide)")
            else:
                print("❌ Fallo en la verificación: el contenido no coincide")
                
    except Exception as e:
        print(f"❌ Error durante la prueba de Django: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_django_upload()
