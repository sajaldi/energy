import os

path = 'd:/Apps/energia/energy/energia/settings.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Filter out the broken lines at the end
new_lines = []
for line in lines:
    if 'N8N_OT_WHATSAPP_WEBHOOK_URL' not in line:
        new_lines.append(line)

# Add the correct one
new_lines.append('\n# Webhook para notificaciones de WhatsApp (n8n)\n')
new_lines.append('N8N_OT_WHATSAPP_WEBHOOK_URL = "http://localhost:5678/webhook-test/ot-whatsapp"\n')

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Settings fixed again.")
