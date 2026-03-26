import sys
import os

file_path = 'mantenimiento/tasks.py'
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
found_try_decode_start = -1
found_try_decode_end = -1

for i, line in enumerate(lines):
    if "def try_decode(content" in line:
        found_try_decode_start = i
        # Find end of function (first line that is not indented and not empty after start)
        for j in range(i + 1, len(lines)):
            if lines[j].strip() != "" and not lines[j].startswith("    "):
                found_try_decode_end = j
                break
        if found_try_decode_end == -1:
            found_try_decode_end = len(lines)
        break

if found_try_decode_start != -1:
    try_decode_code = lines[found_try_decode_start:found_try_decode_end]
    # Remove it from original position
    mid_lines = lines[:found_try_decode_start] + lines[found_try_decode_end:]
    # Insert at top (after imports)
    insertion = 7
    final_lines = mid_lines[:insertion] + ["\n"] + try_decode_code + mid_lines[insertion:]
else:
    final_lines = lines

# Remove the print at the very end if it exists
if final_lines and "Cargando mantenimiento.tasks" in final_lines[-1]:
    final_lines.pop()

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(final_lines)

print("Tasks.py final structure fixed.")
