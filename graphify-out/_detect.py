import json
from graphify.detect import detect
from pathlib import Path

result = detect(Path('.'))
p = Path('graphify-out/.graphify_detect.json')
p.write_text(json.dumps(result), encoding='utf-8')

print('total_files:', result.get('total_files', 0))
print('total_words:', result.get('total_words', 0))
files = result.get('files', {})
for k in ['code','document','paper','image','video']:
    v = files.get(k, [])
    if v:
        print(k + ':', len(v), 'files')
