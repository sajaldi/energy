# test_playwright_opt.py
import os
import sys
import django
import time

# Add current directory to path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

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
        
        print(f"Testing OPTIMIZED PDF generation for OT #{ot.id}...")
        start_time = time.time()
        pdf_bytes = generate_ot_pdf_bytes(ot)
        end_time = time.time()
        
        print(f"Success! Generated {len(pdf_bytes)} bytes in {end_time - start_time:.2f} seconds.")
        
        with open("test_ot_opt.pdf", "wb") as f:
            f.write(pdf_bytes)
        print("File saved as test_ot_opt.pdf")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test()
