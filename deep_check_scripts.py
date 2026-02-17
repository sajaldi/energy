import re
import os

file_path = r'd:\Apps\energia\energy\presupuestos\templates\admin\presupuestos\requisicion\includes\requisicion_scripts.html'

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
        elif tag == 'endif' and stack and stack[-1][0] == 'if':
            stack.pop()
        elif tag == 'endfor' and stack and stack[-1][0] == 'for':
            stack.pop()
        elif tag == 'endblock' and stack and stack[-1][0] == 'block':
            stack.pop()
        elif tag == 'endwith' and stack and stack[-1][0] == 'with':
            stack.pop()
        elif tag not in ['elif', 'else']:
            print(f"Line {line_num}: ERROR! Unexpected {tag} (Stack: {stack})")

if stack:
    print(f"FINISHED with UNCLOSED tags: {stack}")
else:
    print("FINISHED: All tags balanced.")
