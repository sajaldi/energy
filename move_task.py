import sys
import os

file_path = 'mantenimiento/tasks.py'
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

task_decorator = "@shared_task(bind=True)\n"
task_def = "def import_pasos_task"

task_start = -1
task_end = len(lines)

for i, line in enumerate(lines):
    if task_decorator in line and task_def in lines[i+1]:
        task_start = i
        break

if task_start == -1:
    print("Task not found.")
    sys.exit(1)

# Extract task code
task_code = lines[task_start:]

# Remove task code from original lines
new_lines = lines[:task_start]

# Insert task code after imports (around line 7)
insertion_point = 7
for i, line in enumerate(new_lines):
    if "import os" in line or "from django.db" in line:
        insertion_point = i + 1

final_lines = new_lines[:insertion_point] + ["\n"] + task_code + new_lines[insertion_point:]

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(final_lines)

print("Task moved to top.")
