import sys
import os

print(f"CWD: {os.getcwd()}")
print(f"sys.path: {sys.path}")

try:
    import energia
    print("SUCCESS: Imported energia")
    print(f"energia file: {energia.__file__}")
except ImportError as e:
    print(f"FAILURE: Could not import energia: {e}")

try:
    import energia.celery
    print("SUCCESS: Imported energia.celery")
except ImportError as e:
    print(f"FAILURE: Could not import energia.celery: {e}")

try:
    import energy
    print("SUCCESS: Imported energy (unexpected!)")
except ImportError as e:
    print(f"FAILURE: Could not import energy: {e} (Expected)")
