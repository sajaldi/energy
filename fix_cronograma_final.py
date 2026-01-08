#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Script para corregir definitivamente cronograma_grupal.html"""

import os

path = r'd:\Apps\energia\energy\presupuestos\templates\presupuestos\cronograma_grupal.html'

print(f"Abriendo archivo: {path}")

# Leer el archivo
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total de líneas leídas: {len(lines)}")
print(f"Línea 354 ANTES: {repr(lines[353])}")
print(f"Línea 355 ANTES: {repr(lines[354])}")

# Corregir las líneas 354 y 355
# La línea 354 (índice 353) debe ser:
# <td style="color: var(--primary);">{% if val > 0 %}{{ val|floatformat:2|intcomma }}{% else %}-{% endif %}</td>

lines[353] = '                        <td style="color: var(--primary);">{% if val > 0 %}{{ val|floatformat:2|intcomma }}{% else %}-{% endif %}</td>\n'

# Eliminar la línea 355 (índice 354) que contiene solo "endif %}</td>"
del lines[354]

print(f"\nLínea 354 DESPUÉS: {repr(lines[353])}")
print(f"Total de líneas DESPUÉS: {len(lines)}")

# Escribir de vuelta
with open(path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("\n✓ Archivo corregido exitosamente")

# Verificar
with open(path, 'r', encoding='utf-8') as f:
    verify_lines = f.readlines()
    print(f"\nVERIFICACIÓN - Línea 354: {repr(verify_lines[353][:80])}")
    print(f"VERIFICACIÓN - Línea 355: {repr(verify_lines[354][:80])}")
