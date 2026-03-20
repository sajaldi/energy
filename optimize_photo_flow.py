import json
import uuid

filepath = r'd:/Apps/energia/energy/workflow_cierre_ticket.json'

with open(filepath, 'r', encoding='utf-8') as f:
    data = json.load(f)

nodes = data['nodes']
connections = data['connections']

# --- STEP 1: Add IF node for Media Validation ---
# This node goes after 'Variables' and before 'GOWA Download'
if_media_node = {
    "parameters": {
        "conditions": {
            "string": [
                {
                    "value1": "={{ $node[\"Variables\"].json.media_id }}",
                    "operation": "isNotEmpty"
                }
            ]
        }
    },
    "id": str(uuid.uuid4()),
    "name": "Hay Foto?",
    "type": "n8n-nodes-base.if",
    "typeVersion": 1,
    "position": [
        -5500,
        6100
    ]
}
nodes.append(if_media_node)

# --- STEP 2: Update 'Subir Foto (Django)' for Form-Data ---
for node in nodes:
    if node['name'] == 'Subir Foto (Django)':
        node['parameters']['sendBody'] = True
        node['parameters']['bodyContentType'] = 'multipart-form-data'
        node['parameters']['bodyParameters'] = {
            "parameters": [
                {
                    "name": "file",
                    "parameterType": "formBinaryData",
                    "inputDataFieldName": "data"
                }
            ]
        }
        # Clear incompatible parameters if they exist
        node['parameters'].pop('sendBinaryData', None)
        node['parameters'].pop('binaryPropertyName', None)
        print("Updated 'Subir Foto (Django)' to use Form-Data.")

# --- STEP 3: Re-wire connections ---
# The previous logic was: IF -> Escribió Listo? (False) -> Descargar Foto (GOWA)
# We want: IF -> Escribió Listo? (False) -> Hay Foto? (True) -> Descargar Foto (GOWA)

if 'IF -> Escribió Listo?' in connections:
    branches = connections['IF -> Escribió Listo?']['main']
    # Index 1 is the FALSE branch
    old_targets_from_if_listo = branches[1] 
    # Point it to 'Hay Foto?'
    branches[1] = [{
        "node": "Hay Foto?",
        "type": "main",
        "index": 0
    }]
    
    # Connect 'Hay Foto?' (True branch) to 'Descargar Foto (GOWA)'
    connections['Hay Foto?'] = {
        "main": [
            [ # Branch 0 (True)
                {
                    "node": "Descargar Foto (GOWA)",
                    "type": "main",
                    "index": 0
                }
            ],
            [ # Branch 1 (False) - Skip to Confirm/End if no photo
                {
                    "node": "Set -> Confirmar",
                    "type": "main",
                    "index": 0
                }
            ]
        ]
    }
    print("Re-wired connections with 'Hay Foto?' validation.")

# --- Save final workflow ---
with open(filepath, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print("SUCCESS: Photo flow optimized with validation and Form-Data.")
