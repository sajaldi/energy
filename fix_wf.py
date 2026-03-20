import json

try:
    with open('target_workflow.json', 'r', encoding='utf-8-sig') as f:
        data = json.load(f)

    # Find the node "Filtro Anti-Loop1"
    found = False
    for node in data.get('nodes', []):
        if node.get('name') == 'Filtro Anti-Loop1':
            # Update parameters.conditions.boolean[0].value1
            try:
                conds = node['parameters']['conditions']['boolean']
                for cond in conds:
                    if cond.get('value1') == '={{ $json.fromMe }}':
                        cond['value1'] = '={{ !$json.fromMe }}'
                        found = True
                        print("Updated Filtro Anti-Loop1 logic.")
            except (KeyError, IndexError):
                pass

    if not found:
        print("Could not find condition to update in Filtro Anti-Loop1.")

    with open('target_workflow.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
except Exception as e:
    print(f"Error processing JSON: {e}")
    # Read first 100 chars to see what's wrong
    try:
        with open('target_workflow.json', 'rb') as f:
            print(f"First 50 bytes: {f.read(50)}")
    except:
        pass
