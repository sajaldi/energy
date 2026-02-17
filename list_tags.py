import re
import os

file_path = r'd:\Apps\energia\energy\presupuestos\templates\admin\presupuestos\requisicion\requisicion_form.html'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

tags = re.findall(r'\{%\s*([a-z_]+)', content)
print(f"Unique tag keywords in {os.path.basename(file_path)}:")
print(sorted(list(set(tags))))
