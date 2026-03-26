import sys

file_path = 'mantenimiento/tasks.py'
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
in_pasos_task = False

for line in lines:
    if "@shared_task(bind=True, name='mantenimiento.tasks.import_pasos_task')" in line:
        in_pasos_task = True
        # Outdent the decorator
        new_lines.append(line.lstrip())
    elif in_pasos_task:
        if line.strip() == "" or line.startswith("    ") or line.startswith("\t"):
            # Outdent by 4 spaces
            if line.startswith("    "):
                new_lines.append(line[4:])
            else:
                new_lines.append(line)
        else:
            # Reached a line that is NOT indented, so we are out of the task function
            in_pasos_task = False
            new_lines.append(line)
    else:
        new_lines.append(line)

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Indentation fixed.")
