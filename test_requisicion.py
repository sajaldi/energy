import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from presupuestos.models import Requisicion

def test_req_generation():
    print("Testing Requisition generation...")
    try:
        req = Requisicion.objects.create(
            cr8ca_asunto="Test Requisition Automatic Code",
            cr8ca_motivo="Testing logic"
        )
        print(f"Created Requisition: {req.cr8ca_requisicion}")
        print(f"UUID: {req.cr8ca_requisicionid}")
        
        # Check format REQ-XXXXX-YYYY
        import re
        pattern = r'^REQ-\d{5}-\d{4}$'
        if re.match(pattern, req.cr8ca_requisicion):
            print("Format check: PASSED")
        else:
            print(f"Format check: FAILED (got {req.cr8ca_requisicion})")
            
        # Cleanup
        # req.delete()
        # print("Test record deleted.")
            
    except Exception as e:
        print(f"Error during test: {e}")

if __name__ == "__main__":
    test_req_generation()
