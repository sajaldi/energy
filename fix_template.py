import re

path = r'd:\Apps\energia\energy\presupuestos\templates\presupuestos\cronograma_grupal.html'

# Read the file
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the split include tag - match across newlines
pattern = r'{%\s+include\s+"presupuestos/partial_grouped_item\.html"\s+with\s+item=item\s+level=2[\s\n]+group_id="disc-"\|addstr:forloop\.parentloop\.parentloop\.counter\|addstr:"-"\|addstr:forloop\.parentloop\.counter[\s\n]+%}'
replacement = '{% include "presupuestos/partial_grouped_item.html" with item=item level=2 group_id="disc-"|addstr:forloop.parentloop.parentloop.counter|addstr:"-"|addstr:forloop.parentloop.counter %}'

content = re.sub(pattern, replacement, content, flags=re.MULTILINE | re.DOTALL)

# Write back
with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("File fixed successfully")
