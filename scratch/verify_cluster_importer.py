import re

def test_parsing(text):
    print(f"Testing text: {repr(text)}")
    folios_raw = []
    if text.strip():
        folios_raw.extend(re.split(r'[\s,]+', text.strip()))
    folios = list(set([f.strip() for f in folios_raw if f.strip()]))
    print(f"Result: {folios}")
    return folios

test_parsing("SS26-144555, SS26-144556")
test_parsing("SS26-144555 SS26-144556\nSS26-144557")
test_parsing("  SS26-144555 ,   SS26-144556  ")
test_parsing("12345, 67890")
