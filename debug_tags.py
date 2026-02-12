
import re

def debug_tags(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find all django tags
    tags = re.findall(r'({%\s*([a-z_/]+).*?%})', content, re.DOTALL)
    
    stack = []
    block_tags = {'if', 'for', 'block', 'with', 'comment', 'filter', 'spaceless'}

    print(f"Total tags found: {len(tags)}")
    
    for full_tag, tag_name in tags:
        if tag_name.startswith('end'):
            base = tag_name[3:]
            if not stack:
                print(f"Unmatched end tag: {full_tag}")
                continue
            
            last = stack[-1]
            if last['name'] == base:
                stack.pop()
            else:
                # Potential mismatch
                print(f"Mismatch: found {full_tag}, expected end for {stack[-1]['full']}")
                # Try to find matching one in stack
                for i in range(len(stack)-1, -1, -1):
                    if stack[i]['name'] == base:
                        # Pop until here
                        while len(stack) > i:
                            stack.pop()
                        break
        elif tag_name in ['elif', 'else']:
            # Should be inside an if
            found_if = face_tag_in_stack(stack, 'if')
            if not found_if:
                print(f"Found {full_tag} outside of an if block")
        elif tag_name in block_tags:
            stack.append({'name': tag_name, 'full': full_tag})

    if stack:
        print("Unclosed tags:")
        for s in stack:
            print(f"  {s['full']}")
    else:
        print("All tags matched.")

def face_tag_in_stack(stack, name):
    for s in stack:
        if s['name'] == name: return True
    return False

debug_tags(r"d:\Apps\energia\energy\presupuestos\templates\admin\presupuestos\requisicion\requisicion_form.html")
