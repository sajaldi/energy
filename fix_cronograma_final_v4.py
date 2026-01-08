
import os
import re

file_path = r'd:\Apps\energia\energy\presupuestos\templates\presupuestos\cronograma_grupal.html'

print(f"Checking {file_path}")

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Fix the split IF tag logic
# We look for the specific broken pattern: {% else %}-{% <newline> endif %}
# or any variation where {% else %}-{% is at the end of a line
fixed_content = re.sub(r'{% else %}-{%[\s\r\n]+endif %}', '{% else %}-{% endif %}', content)

# 2. Fix the split INCLUDE tag logic
# Search for includes that span multiple lines
fixed_content = re.sub(r'\{%\s*include\s*"presupuestos/partial_grouped_item\.html"[^%]*?%\}(?!\n)', 
                       '{% include "presupuestos/partial_grouped_item.html" with item=item level=2 group_id="disc-"|addstr:forloop.parentloop.parentloop.counter|addstr:"-"|addstr:forloop.parentloop.counter %}\n', 
                       fixed_content, flags=re.DOTALL)
                       
# Manual cleanup if regex misses (safety net)
if '{% else %}-{%' in fixed_content and '{% endif %}' not in fixed_content.split('{% else %}-{%')[1][:20]:
   print("WARNING: Regex didn't catch the split IF. Applying valid manual replace.")
   fixed_content = fixed_content.replace('{% else %}-{%', '{% else %}-{% endif %}')
   fixed_content = fixed_content.replace('                            endif %}', '') # Remove orphan endif line if exists

# Manual cleanup for include artifacts 
# If we see multiple inclusions or text artifacts, we might want to just force the line
lines = fixed_content.splitlines()
new_lines = []
skip_next = False
for i, line in enumerate(lines):
    if skip_next:
        skip_next = False
        continue
        
    # Check for the Discipline loop IF split
    if 'pd.proyeccion_total_mensual' in lines[i-1] if i>0 else False:
        # We are likely at the line. Let's ensure it's clean.
        if '{% if val > 0 %}' in line and 'endif' not in line:
            # It's split. Join with next.
            print(f"Fixing split IF at line {i+1}")
            combined = line.strip() + (lines[i+1].strip() if i+1 < len(lines) else "")
            # Clean up the join
            combined = combined.replace('{% else %}-{%endif %}', '{% else %}-{% endif %}')
            combined = combined.replace('{% else %}-{% endif %}', '{% else %}-{% endif %}') # normalize
            new_lines.append('                        <td style="color: var(--primary);">{% if val > 0 %}{{ val|floatformat:2|intcomma }}{% else %}-{% endif %}</td>')
            skip_next = True 
            continue
            
    new_lines.append(line)

final_content = '\n'.join(new_lines)

# Write back
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(final_content)
    
print("File processing complete.")

# Verify
with open(file_path, 'r', encoding='utf-8') as f:
    verify_lines = f.readlines()
    for i, line in enumerate(verify_lines):
        if 'pd.proyeccion_total_mensual' in verify_lines[i-1] if i>0 else False:
             print(f"Line {i+1} content: {line.strip()}")
