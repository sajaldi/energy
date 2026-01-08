import re
import os

path = r'd:\Apps\energia\energy\presupuestos\templates\presupuestos\cronograma_grupal.html'
print(f"Reading {path}...")

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern to match the split include tag. 
# It likely has newlines and extra spaces.
pattern = r'{%\s+include\s+"presupuestos/partial_grouped_item\.html"\s+with\s+item=item\s+level=2\s+group_id="disc-"\|addstr:forloop\.parentloop\.parentloop\.counter\|addstr:"-"\|addstr:forloop\.parentloop\.counter\s+%}'

# Since the previous grep showed the lines are definitely split, let's look for the specific strings and verify if we can match them with a wider regex allowing for whitespace/newlines
# The 'repr' output showed:
# 361: '                    {% include "presupuestos/partial_gro...
# ...
# So let's construct a pattern that matches the start and end tokens flexibly.

# We want to replace the entire block with a single line version.
replacement = '{% include "presupuestos/partial_grouped_item.html" with item=item level=2 group_id="disc-"|addstr:forloop.parentloop.parentloop.counter|addstr:"-"|addstr:forloop.parentloop.counter %}'

# Using re.sub with DOTALL to match across newlines
# We'll match specifically the include tag logic
regex_pattern = r'\{%\s*include\s*"presupuestos/partial_grouped_item\.html"\s*with\s*item=item\s*level=2.*?%\}'

new_content = re.sub(regex_pattern, replacement, content, flags=re.DOTALL)

if new_content == content:
    print("No changes were made. Pattern might not have matched.")
    # Let's try a more specific find/replace if regex fails, simply identifying the block by start/end index if found
    start_marker = '{% include "presupuestos/partial_grouped_item.html" with item=item level=2'
    end_marker = '%}'
    
    # This is risky if there are multiple, but here there is only one such specific include
    start_idx = content.find(start_marker)
    if start_idx != -1:
        # Find the closing %} after the start
        end_idx = content.find(end_marker, start_idx)
        if end_idx != -1:
            print(f"Found block by string search at {start_idx}-{end_idx+2}")
            # Replace the range
            new_content = content[:start_idx] + replacement + content[end_idx+2:]
        else:
            print("Could not find closing tag.")
    else:
        print("Could not find starting tag.")
else:
    print("Regex replacement successful.")

if new_content != content:
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("File saved.")
else:
    print("File content unchanged.")
