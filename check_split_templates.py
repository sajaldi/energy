import re
import os

files_to_check = [
    r'd:\Apps\energia\energy\presupuestos\templates\admin\presupuestos\requisicion\requisicion_form.html',
    r'd:\Apps\energia\energy\presupuestos\templates\admin\presupuestos\requisicion\includes\requisicion_styles.html',
    r'd:\Apps\energia\energy\presupuestos\templates\admin\presupuestos\requisicion\includes\requisicion_modals.html',
    r'd:\Apps\energia\energy\presupuestos\templates\admin\presupuestos\requisicion\includes\requisicion_scripts.html'
]

for file_path in files_to_check:
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        continue
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find all if/endif, for/endfor, block/endblock
    # Improved regex to handle spaces and newlines (though split across lines is what we want to find)
    tags = re.findall(r'\{%\s*(if|endif|for|endfor|block|endblock|elif|else)\b', content)
    
    nest = []
    print(f"Checking {os.path.basename(file_path)}...")
    
    lines = content.splitlines()
    for i, line in enumerate(lines):
        line_num = i + 1
        # Extract potential tags, also look for partial tags that might indicate splitting
        t = re.findall(r'\{%\s*(if|endif|for|endfor|block|endblock|elif|else)\b', line)
        for tag in t:
            if tag in ['if', 'for', 'block']:
                nest.append((tag, line_num))
            elif tag == 'endif':
                if not nest or nest[-1][0] != 'if':
                    print(f"  ERROR: extra endif at {line_num} in {os.path.basename(file_path)}. Nest stack: {nest}")
                    # Don't pop if empty to avoid crash, but index error is handled by if not nest
                    if nest: nest.pop()
                else:
                    nest.pop()
            elif tag == 'endfor':
                if not nest or nest[-1][0] != 'for':
                    print(f"  ERROR: extra endfor at {line_num} in {os.path.basename(file_path)}. Nest stack: {nest}")
                    if nest: nest.pop()
                else:
                    nest.pop()
            elif tag == 'endblock':
                if not nest or nest[-1][0] != 'block':
                    print(f"  ERROR: extra endblock at {line_num} in {os.path.basename(file_path)}. Nest stack: {nest}")
                    if nest: nest.pop()
                else:
                    nest.pop()
        
        # Check for split tags (e.g., {% endif without %} on same line)
        if '{%' in line and '%}' not in line:
            print(f"  WARNING: Potential split tag at line {line_num}: {line}")
        if '%}' in line and '{%' not in line:
            # This is okay if it's text, but if it's closing a tag from previous line...
            pass

    if nest:
        print(f"  UNCLOSED in {os.path.basename(file_path)}: {nest}")
    else:
        print(f"  {os.path.basename(file_path)} looks BALANCED.")
