import os
import django
from django.test import RequestFactory
from django.urls import reverse

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from documentos.views import documento_detalle_json
from documentos.models import Documento

def test_api():
    try:
        doc = Documento.objects.first()
        if not doc:
            print("No hay documentos en la base de datos.")
            return
        
        factory = RequestFactory()
        url = reverse('documentos:documento_detalle_json', args=[doc.id])
        request = factory.get(url)
        
        # Simular usuario logueado
        from django.contrib.auth.models import User
        user = User.objects.filter(is_superuser=True).first()
        request.user = user
        
        response = documento_detalle_json(request, doc.id)
        print(f"Status: {response.status_code}")
        print(f"Content: {response.content.decode('utf-8')}")
    except Exception as e:
        print(f"Error en el test: {str(e)}")

if __name__ == "__main__":
    test_api()
