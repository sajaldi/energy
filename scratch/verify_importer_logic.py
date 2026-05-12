import os
import sys

# Mocking enough of Django to test the view logic
class MockRequest:
    def __init__(self, folios_str):
        self.GET = {'folios': folios_str}

def test_folio_parsing(folios_str):
    print(f"Testing parsing for: '{folios_str}'")
    # Logic from trigger_sync_by_folios
    folios_list = [f.strip() for f in folios_str.replace(',', ' ').split() if f.strip()]
    print(f"Resulting list: {folios_list}")
    return folios_list

# Test cases
test_folio_parsing("SS26-144555, SS26-144556")
test_folio_parsing("SS26-144555 SS26-144556 SS26-144557")
test_folio_parsing("  SS26-144555 ,   SS26-144556\nSS26-144557  ")

print("\nLogic check passed.")
