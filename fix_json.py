import json
import os

filepath = r'd:/Apps/energia/energy/workflow_cierre_ticket.json'
try:
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    
    # Revert the broken syntax that injected unescaped quotes
    # The broken syntax was like $["Variables"] inside a JSON string
    # We want to change it back to $('Variables') which is safe for JSON simple strings
    # or n8n style notation.
    fixed_content = content.replace('$["Variables"]', "$('Variables')")
    
    # Also ensure there are no other accidental broken quotes
    # Validate it as JSON after fixing
    data = json.loads(fixed_content)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    print("SUCCESS: JSON fixed and validated.")
except Exception as e:
    print(f"ERROR: {e}")
