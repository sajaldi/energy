
filepath = r"d:\Apps\energia\energy\presupuestos\templates\admin\presupuestos\requisicion\requisicion_form.html"
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Aggressive replacement of the broken tag
target = """    <form method="post" enctype="multipart/form-data" id="wizard-form" novalidate {% if is_readonly %}disabled{% endif\n        %}>"""
replacement = """    <form method="post" enctype="multipart/form-data" id="wizard-form" novalidate {% if is_readonly %}disabled{% endif %}>"""

if target in content:
    new_content = content.replace(target, replacement)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Replacement successful via Python script.")
else:
    print("Target NOT found in content via Python script.")
    # Fallback search for a more flexible version
    import re
    # Match {% if is_readonly %}disabled{% endif followed by newline and optional whitespace and %}>
    new_content, count = re.subn(r'{%\s*if\s+is_readonly\s*%}disabled{%\s*endif\s*\n\s*%}>', r'{% if is_readonly %}disabled{% endif %}>', content)
    if count > 0:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Replacement successful via regex. Replaced {count} instances.")
    else:
        print("Regex replacement also failed.")
