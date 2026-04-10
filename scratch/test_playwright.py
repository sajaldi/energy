# test_playwright.py
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energy.settings')
django.setup()

from mantenimiento.models import OrdenTrabajo
from mantenimiento.utils.pdf_utils import generate_ot_pdf_bytes

def test():
    try:
        ot = OrdenTrabajo.objects.first()
        if not ot:
            print("No OTs found to test.")
            return
        
        print(f"Testing PDF generation for OT #{ot.id}...")
        pdf_bytes = generate_ot_pdf_bytes(ot)
        print(f"Success! Generated {len(pdf_bytes)} bytes.")
        
        with open("test_ot.pdf", "wb") as f:
            f.write(pdf_bytes)
        print("File saved as test_ot.pdf")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test()
