import os

path = 'd:/Apps/energia/energy/energia/settings.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if 'N8N_OT_WHATSAPP_WEBHOOK_URL' not in line:
        new_lines.append(line)

new_lines.append('\n# Webhook para notificaciones de n8n (Generico)\n')
new_lines.append('N8N_OT_WHATSAPP_WEBHOOK_URL = "http://localhost:5678/webhook-test/notificar-ot"\n')

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Settings updated to notificar-ot.")
