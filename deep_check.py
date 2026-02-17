import re
import os

file_path = r'd:\Apps\energia\energy\presupuestos\templates\admin\presupuestos\requisicion\requisicion_form.html'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern for all tags
tag_pattern = re.compile(r'\{%\s*(if|endif|for|endfor|block|endblock|elif|else|with|endwith)\b')

stack = []
print(f"Analyzing {file_path}...")

for i, line in enumerate(content.splitlines()):
    line_num = i + 1
    matches = tag_pattern.finditer(line)
    for match in matches:
        tag = match.group(1)
        if tag in ['if', 'for', 'block', 'with']:
            stack.append((tag, line_num))
            print(f"Line {line_num}: Open {tag}")
        elif tag == 'endif':
            if not stack or stack[-1][0] != 'if':
                print(f"Line {line_num}: ERROR! Unexpected endif (Stack: {stack})")
            else:
                top = stack.pop()
                print(f"Line {line_num}: Close {top[0]} from line {top[1]}")
        elif tag == 'endfor':
            if not stack or stack[-1][0] != 'for':
                print(f"Line {line_num}: ERROR! Unexpected endfor (Stack: {stack})")
            else:
                top = stack.pop()
                print(f"Line {line_num}: Close {top[0]} from line {top[1]}")
        elif tag == 'endblock':
            if not stack or stack[-1][0] != 'block':
                print(f"Line {line_num}: ERROR! Unexpected endblock (Stack: {stack})")
            else:
                top = stack.pop()
                print(f"Line {line_num}: Close {top[0]} from line {top[1]}")
        elif tag == 'endwith':
            if not stack or stack[-1][0] != 'with':
                print(f"Line {line_num}: ERROR! Unexpected endwith (Stack: {stack})")
            else:
                top = stack.pop()
                print(f"Line {line_num}: Close {top[0]} from line {top[1]}")
        elif tag in ['elif', 'else']:
             print(f"Line {line_num}: Branch {tag}")

if stack:
    print(f"FINISHED with UNCLOSED tags: {stack}")
else:
    print("FINISHED: All tags balanced.")
