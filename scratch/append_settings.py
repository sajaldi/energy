import os

path = 'd:/Apps/energia/energy/energia/settings.py'
with open(path, 'r', encoding='utf-8') as f:
    data = f.read()

# Just append to the end
if 'WEBPUSH_SETTINGS' not in data:
    data += """
# Configuración de Web Push Notifications
WEBPUSH_SETTINGS = {
    "VAPID_PUBLIC_KEY": "BBjNVFg9HiiToaOsEDKzXXAdWa7vaWd-su_A9zVm5MwVeisPRkOVUO7FFMIn58fIt4CtDzRxyj14PDYitSGutkE",
    "VAPID_PRIVATE_KEY": "14u5SuyBRhIfkUGJmRneQBhM493XS8d3cETeYBAbymg",
    "VAPID_ADMIN_EMAIL": "admin@energia-dcc.com"
}
"""

with open(path, 'w', encoding='utf-8') as f:
    f.write(data)

print("Settings appended.")
