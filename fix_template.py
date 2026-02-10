#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Script de fuerza bruta EXTREMA para arreglar el template"""

import re

template_path = r"d:\Apps\energia\energy\presupuestos\templates\admin\presupuestos\requisicion\requisicion_form.html"

print(f"Leyendo archivo: {template_path}")
with open(template_path, 'r', encoding='utf-8') as f:
    content = f.read()

print(f"Tamaño original: {len(content)} caracteres")

# Usar regex para encontrar y reemplazar CUALQUIER variación
# Patrón: {{ variable | yesno: "valor" }} o cualquier combinación de espacios
pattern = r'\{\{\s*(\w+)\s*\|\s*yesno\s*:\s*"([^"]+)"\s*\}\}'
replacement = r'{{ \1|yesno:"\2" }}'

matches = re.findall(pattern, content)
if matches:
    print(f"\nEncontrados {len(matches)} patrones a corregir:")
    for var, val in matches[:10]:  # Mostrar primeros 10
        print(f"  - Variable: {var}, Valor: {val}")

# Hacer el reemplazo
new_content = re.sub(pattern, replacement, content)

changes = len(matches)
print(f"\nTotal de cambios: {changes}")

if changes > 0:
    print(f"Guardando archivo...")
    with open(template_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("✅ Archivo guardado exitosamente!")
    
    # Verificar
    print("\nVerificando resultado...")
    with open(template_path, 'r', encoding='utf-8') as f:
        verify = f.read()
    
    remaining = re.findall(pattern, verify)
    if remaining:
        print(f"⚠️ Todavía quedan {len(remaining)} patrones sin corregir")
    else:
        print("✅ ¡Todos los patrones corregidos!")
        
    # Mostrar las líneas corregidas
    print("\nLíneas corregidas en el archivo:")
    lines = new_content.split('\n')
    for i, line in enumerate(lines, 1):
        if '|yesno:"true,false"' in line:
            print(f"  Línea {i}: {line.strip()[:80]}...")
else:
    print("⚠️ No se encontraron patrones que corregir")

print("\n✅ Script completado!")
