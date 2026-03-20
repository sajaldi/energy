import json
import subprocess

wf_id = "mNnJ3JL47Qn4sVkM"
api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwOTM0MjU4Ni1jN2MzLTQ2ZjEtYmE1Mi00MjE3OTBkYWU0ZmQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiMjgzODliZjYtZGQxMC00NWIxLWI4ODAtZTJmMjA3ODIzNzhjIiwiaWF0IjoxNzczODQ1OTQ0fQ.13ueEws9HHdUdiO8ejyHSZsebjnuG_PSIzvmzcFzQrk"
url = f"http://181.115.47.107:5678/api/v1/workflows/{wf_id}"

with open('target_workflow.json', 'r', encoding='utf-8-sig') as f:
    data = json.load(f)

# Push everything as is
cmd = [
    "curl.exe", "-v", "-X", "PUT", url,
    "-H", f"X-N8N-API-KEY: {api_key}",
    "-H", "Content-Type: application/json",
    "-d", "@target_workflow.json"
]

result = subprocess.run(cmd, capture_output=True, text=True)
print(f"STDOUT: {result.stdout}")
print(f"STDERR: {result.stderr}")
