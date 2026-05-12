import os
import django
import sys

# Setup Django
sys.path.append('d:\\Apps\\energia\\energy')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from callcenter.models import SolicitudTicket
from django.db.models import Q

def test_search(query):
    print(f"Testing search with query: '{query}'")
    try:
        # Simulate logic in views
        search_q = Q(folio__icontains=query) | Q(solicitante__icontains=query) | Q(solicitud_descripcion__icontains=query)
        if query.isdigit():
            search_q |= Q(id_solicitud=query)
        
        # This should NOT crash
        count = SolicitudTicket.objects.filter(search_q).count()
        print(f"Success! Found {count} results.")
        return True
    except ValueError as e:
        print(f"FAILED: Caught ValueError: {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return False

if __name__ == "__main__":
    test_1 = test_search("Tickets")
    test_2 = test_search("12345")
    
    if test_1 and test_2:
        print("\nAll tests passed! The search logic is robust.")
        sys.exit(0)
    else:
        print("\nSome tests failed.")
        sys.exit(1)
