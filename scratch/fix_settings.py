import os

path = 'd:/Apps/energia/energy/energia/settings.py'
with open(path, 'rb') as f:
    data = f.read().decode('latin-1', errors='ignore')

# Remove the broken section
if '# Config' in data:
    data = data.split('# Config')[0]

# Append the correct one
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

print("Settings fixed.")
