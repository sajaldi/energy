import os
import sys

# Mocking enough of Django to test Q object logic
class MockQ:
    def __init__(self, **kwargs):
        self.children = list(kwargs.items())
    def __or__(self, other):
        new_q = MockQ()
        new_q.children = self.children + other.children
        return new_q
    def __repr__(self):
        return f"Q({self.children})"

def test_logic(query):
    print(f"Testing logic with query: '{query}'")
    
    # Simulate logic in views
    # We want to ensure id_solicitud is only present if query is digit
    
    q_objects = []
    q_objects.append(('folio__icontains', query))
    
    if query.isdigit():
        q_objects.append(('id_solicitud', query))
    
    print(f"Resulting filters: {q_objects}")
    
    # Check if id_solicitud is present when it shouldn't be
    has_id_solicitud = any(k == 'id_solicitud' for k, v in q_objects)
    
    if query == "Tickets" and has_id_solicitud:
        print("FAILED: id_solicitud included for non-numeric query")
        return False
    if query == "12345" and not has_id_solicitud:
        print("FAILED: id_solicitud NOT included for numeric query")
        return False
        
    print("Success!")
    return True

if __name__ == "__main__":
    test_1 = test_logic("Tickets")
    test_2 = test_logic("12345")
    
    if test_1 and test_2:
        print("\nLogic verification passed!")
        sys.exit(0)
    else:
        print("\nLogic verification failed.")
        sys.exit(1)
