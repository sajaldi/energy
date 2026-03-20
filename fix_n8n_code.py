import json
import uuid

filepath = r'd:/Apps/energia/energy/workflow_cierre_ticket.json'

with open(filepath, 'r', encoding='utf-8') as f:
    data = json.load(f)

nodes = data['nodes']

# Correct Javascript parsing code
# Use double backslashes for JS regex escape sequences to survive Python string parsing
code_js = r"""
const msg = $node["Variables"].json.mensaje_original || "";

function extract(regex, defaultVal = "") {
  const match = msg.match(regex);
  return (match && match[1]) ? match[1].trim() : defaultVal;
}

// Regex more robust as suggested by user
const diagnostico = extract(/Diagn[oó]stico:[ ]*([^\n\r-]+)/i, msg);
const actividades = extract(/Acci[oó]n realizada:[ ]*([^\n\r-]+)/i, "Ver diagnóstico");
const hi_str = extract(/HI:[ ]*([^\n\r-]+)/i, "");
const hf_str = extract(/HF:[ ]*([^\n\r-]+)/i, "");
const observaciones = extract(/Observa[cv]iones:[ ]*([^\n\r-]+)/i, "Ninguna");
const uf = extract(/UF:[ ]*([^\n\r-]+)/i, "N/A");

return {
  diagnostico,
  actividades,
  hi_str,
  hf_str,
  observaciones,
  uf
};
"""

for node in nodes:
    if node['name'] == 'Parsear Bloque Cierre':
        node['parameters']['jsCode'] = code_js
        print("FIXED: 'Parsear Bloque Cierre' jsCode.")

with open(filepath, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print("SUCCESS: Workflow fixed.")
