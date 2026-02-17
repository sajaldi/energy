import os

files = [
    r'd:\Apps\energia\energy\presupuestos\templates\admin\presupuestos\requisicion\requisicion_form.html',
    r'd:\Apps\energia\energy\presupuestos\templates\admin\presupuestos\requisicion\includes\requisicion_styles.html',
    r'd:\Apps\energia\energy\presupuestos\templates\admin\presupuestos\requisicion\includes\requisicion_modals.html',
    r'd:\Apps\energia\energy\presupuestos\templates\admin\presupuestos\requisicion\includes\requisicion_scripts.html'
]

for file_path in files:
    if not os.path.exists(file_path): continue
    print(f"Checking {os.path.basename(file_path)}...")
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        line_num = i + 1
        if '{%' in line and '%}' not in line:
            print(f"  SPLIT START at line {line_num}: {line.strip()}")
        if '%}' in line and '{%' not in line:
            # Check if it was preceded by a split start (actually just looking for suspicious content)
            if 'endif' in line or 'endfor' in line or 'endblock' in line or 'else' in line:
                print(f"  SPLIT END at line {line_num}: {line.strip()}")

print("Done.")
