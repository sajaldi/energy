import unicodedata

def try_decode(content, encodings=['utf-8-sig', 'iso-8859-1', 'windows-1252', 'utf-8']):
    for encoding in encodings:
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode('utf-8', errors='ignore')

# Simular "mecánico" en diferentes encodings
test_str = "mecánico"
encodings_to_test = ['utf-8', 'iso-8859-1', 'windows-1252']

print(f"Original: {test_str}")
print("-" * 30)

for enc in encodings_to_test:
    content = test_str.encode(enc)
    decoded = try_decode(content)
    print(f"Encoded as {enc:12} | Decoded as: {decoded}")
    
    # Simular lo que pasaría si lo forzamos a iso-8859-1 siendo utf-8
    if enc == 'utf-8':
        bad_decoded = content.decode('iso-8859-1')
        print(f"FORCED UTF-8 to ISO-8859-1: {bad_decoded}")

print("-" * 30)
# Qué produce ?? ?
# A veces es la base de datos cuando recibe algo que no puede representar
# O si hacemos errors='replace'
content_bad = b'mec\xe1nico' # ISO-8859-1 'á'
decoded_replace = content_bad.decode('utf-8', errors='replace')
print(f"ISO bytes decoded as UTF-8 (replace): {decoded_replace}")
