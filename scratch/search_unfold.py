import os

workspace = r"d:\Apps\energia\energy"
found = []

for root, dirs, files in os.walk(workspace):
    # Skip virtual environments and git
    if any(p in root for p in ['venv', 'env', '.git', '__pycache__', 'node_modules', '.agent']):
        continue
    for file in files:
        if file.endswith(('.py', '.html', '.css', '.js', '.json', '.sh', '.bat', '.ini', '.cfg', '.yml', '.yaml', '.txt')):
            path = os.path.join(root, file)
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    if 'unfold' in content.lower():
                        found.append(path)
            except Exception as e:
                pass

print("Files containing 'unfold':")
for p in found:
    print(p)
