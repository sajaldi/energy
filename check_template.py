
import re

def check_template_balance(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"Error: File {filepath} not found.")
        return

    stack = []
    
    # Tags that have an end tag
    block_tags = {'if', 'for', 'block', 'with', 'comment', 'filter', 'spaceless'}

    for i, line in enumerate(lines):
        line_num = i + 1
        # Use findall to get all tags in the line
        matches = re.findall(r'{%\s*(/?[a-z_]+)', line)
        
        for tag_name in matches:
            if tag_name.startswith('end'):
                base_tag = tag_name[3:]
                if not stack:
                    print(f"Error at line {line_num}: Found enclosed {{% {tag_name} %}} but stack is empty")
                    continue
                
                last = stack[-1]
                if last['tag'] == base_tag:
                    stack.pop()
                elif tag_name in ['elif', 'else'] and last['tag'] == 'if':
                    # Part of if block, don't pop
                    pass
                elif tag_name == 'empty' and last['tag'] == 'for':
                    # Part of for block
                    pass
                else:
                    # Likely a mismatch or nested error
                    # Check if this end tag belongs to something else in the stack
                    found_match = False
                    for idx in range(len(stack)-1, -1, -1):
                        if stack[idx]['tag'] == base_tag:
                            # Pop everything above it and this as well
                            while len(stack) > idx:
                                item = stack.pop()
                                print(f"Warning: Auto-closing un-closed {{% {item['tag']} %}} from line {item['line']} because encountered {{% {tag_name} %}} at line {line_num}")
                            found_match = True
                            break
                    if not found_match:
                         print(f"Error at line {line_num}: Found {{% {tag_name} %}} but expected closing for {{% {last['tag']} %}} (opened at line {last['line']})")
            
            elif tag_name in block_tags:
                stack.append({'tag': tag_name, 'line': line_num})
    
    if stack:
        print("Unclosed tags at EOF:")
        for s in stack:
            print(f"  {{% {s['tag']} %}} opened at line {s['line']}")
    else:
        print("Template seems balanced.")

check_template_balance(r"d:\Apps\energia\energy\presupuestos\templates\admin\presupuestos\requisicion\requisicion_form.html")
