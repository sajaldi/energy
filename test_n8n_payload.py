"""
Script de prueba para verificar el payload que Django envía a n8n
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from django.conf import settings
from documentos.models import Documento

# Obtener un documento de prueba (el ID 22 que se ve en la imagen)
try:
    doc = Documento.objects.get(id=22)
    
    print("=" * 60)
    print("PAYLOAD QUE DJANGO ENVÍA A N8N:")
    print("=" * 60)
    
    payload = {
        'documento_id': doc.id,
        'codigo': doc.codigo,
        'filepath': doc.ultima_revision.archivo.name if doc.ultima_revision else "N/A",
        'callback_url': f"{settings.SITE_URL}/documentos/api/update-texto/{doc.id}/"
    }
    
    import json
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    
    print("\n" + "=" * 60)
    print("CONFIGURACIÓN ACTUAL:")
    print("=" * 60)
    print(f"SITE_URL: {settings.SITE_URL}")
    print(f"N8N_EXTRACT_TEXTO_WEBHOOK_URL: {settings.N8N_EXTRACT_TEXTO_WEBHOOK_URL}")
    print("\n" + "=" * 60)
    print("CALLBACK URL QUE N8N DEBE USAR:")
    print("=" * 60)
    print(f"✅ {payload['callback_url']}")
    print("\n❌ NO USAR: http://localhost:5000/documentos/api/update-texto/22/")
    print("=" * 60)
    
except Documento.DoesNotExist:
    print("❌ No se encontró el documento con ID 22")
    print("Probando con el primer documento disponible...")
    doc = Documento.objects.first()
    if doc:
        payload = {
            'documento_id': doc.id,
            'codigo': doc.codigo,
            'filepath': doc.ultima_revision.archivo.name if doc.ultima_revision else "N/A",
            'callback_url': f"{settings.SITE_URL}/documentos/api/update-texto/{doc.id}/"
        }
        import json
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print("❌ No hay documentos en la base de datos")
