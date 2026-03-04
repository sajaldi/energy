import sys, re

# === 1. views/mobile.py ===
with open('d:/Apps/energia/energy/mantenimiento/views/mobile.py', 'r', encoding='utf-8') as f:
    text = f.read()
text = text.replace('PasoProcedimiento', 'PasoRutina')
with open('d:/Apps/energia/energy/mantenimiento/views/mobile.py', 'w', encoding='utf-8') as f:
    f.write(text)

# === 2. tasks.py ===
with open('d:/Apps/energia/energy/mantenimiento/tasks.py', 'r', encoding='utf-8') as f:
    text = f.read()

# I will comment out the import block and execution for procedimientos
text = re.sub(r'def import_procedimientos_task\([\s\S]*?    except Exception as e:\n        return False', 'def import_procedimientos_task(*args, **kwargs):\n    return False\n', text)
with open('d:/Apps/energia/energy/mantenimiento/tasks.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Views updated.")
