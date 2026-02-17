import re

with open(r'd:\Apps\energia\energy\presupuestos\templates\admin\presupuestos\requisicion\requisicion_form.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Match all template tags
tags = re.findall(r'\{%\s*(if|endif|for|endfor|block|endblock|elif|else)\b', content)

nest = []
counts = {'if': 0, 'endif': 0, 'for': 0, 'endfor': 0, 'block': 0, 'endblock': 0}

for tag in tags:
    if tag in counts:
        counts[tag] += 1
    
    if tag in ['if', 'for', 'block']:
        nest.append(tag)
    elif tag == 'endif':
        if nest and nest[-1] == 'if':
            nest.pop()
    elif tag == 'endfor':
        if nest and nest[-1] == 'for':
            nest.pop()
    elif tag == 'endblock':
        if nest and nest[-1] == 'block':
            nest.pop()

print(f"Counts: {counts}")
print(f"Unclosed at end: {nest}")

# Find WHERE it breaks
nest = []
lines = content.splitlines()
for i, line in enumerate(lines):
    line_num = i + 1
    t = re.findall(r'\{%\s*(if|endif|for|endfor|block|endblock|elif|else)\b', line)
    for tag in t:
        if tag in ['if', 'for', 'block']:
            nest.append((tag, line_num))
        elif tag == 'endif':
            if not nest or nest[-1][0] != 'if':
                print(f"ERROR: endif at {line_num} but nest is {nest}")
                if nest: nest.pop()
            else:
                nest.pop()
        elif tag == 'endfor':
            if not nest or nest[-1][0] != 'for':
                print(f"ERROR: endfor at {line_num} but nest is {nest}")
                if nest: nest.pop()
            else:
                nest.pop()
        elif tag == 'endblock':
            if not nest or nest[-1][0] != 'block':
                print(f"ERROR: endblock at {line_num} but nest is {nest}")
                if nest: nest.pop()
            else:
                nest.pop()
