
import os
import django
import sys

# Setup django
sys.path.append('D:\\Apps\\energia\\energy')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from documentos.mayan_client import MayanEDMSClient
from django.conf import settings

def test_mayan():
    print(f"Testing Mayan at: {settings.MAYAN_EDMS_API_URL}")
    client = MayanEDMSClient()
    try:
        types = client.get_document_types()
        print("Successfully connected to Mayan!")
        print(f"Document Types found: {len(types.get('results', []))}")
        for t in types.get('results', []):
            print(f" - {t['label']} (ID: {t['id']})")
    except Exception as e:
        print(f"Failed to connect: {e}")

if __name__ == "__main__":
    test_mayan()
