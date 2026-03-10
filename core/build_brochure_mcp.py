import json
import http.client
import time

def call_mcp(action, params=None):
    conn = http.client.HTTPConnection("localhost", 8013)
    payload = json.dumps({
        "action": action,
        "params": params or {}
    })
    headers = {'Content-Type': 'application/json'}
    conn.request("POST", "/", payload, headers)
    response = conn.getresponse()
    data = response.read().decode('utf-8')
    conn.close()
    return json.loads(data)

print("Iniciando diseño de brochure vía MCP...")

# 1. Nuevo documento 11x17in (a 96 DPI: 1632x1056 px)
call_mcp("new_document", {"width": 1632, "height": 1056, "units": "px"})

# 2. Agregar gradientes y patterns (vía RAW SVG para simplicidad en defs complejos)
defs_svg = """
<defs>
    <linearGradient id="grad_hero" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0f0c29" />
      <stop offset="50%" stop-color="#302b63" />
      <stop offset="100%" stop-color="#24243e" />
    </linearGradient>
    <linearGradient id="grad_accent" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#f093fb" />
      <stop offset="100%" stop-color="#f5576c" />
    </linearGradient>
    <linearGradient id="grad_card" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#ffffff" />
      <stop offset="100%" stop-color="#f1f3f5" />
    </linearGradient>
    <pattern id="dots" x="0" y="0" width="20" height="20" patternUnits="userSpaceOnUse">
      <circle cx="10" cy="10" r="1.5" fill="rgba(255,255,255,0.08)" />
    </pattern>
</defs>
"""
call_mcp("add_raw_svg", {"svg": defs_svg})

# 3. SECCIÓN 1: HERO
call_mcp("add_rect", {"x": 0, "y": 0, "width": 544, "height": 1056, "fill": "url(#grad_hero)"})
call_mcp("add_rect", {"x": 0, "y": 0, "width": 544, "height": 1056, "fill": "url(#dots)"})

# Logo Hexagonal
logo_svg = """
<g transform="translate(272, 280)">
  <polygon points="0,-65 56,-32 56,32 0,65 -56,32 -56,-32" fill="none" stroke="url(#grad_accent)" stroke_width="2.5" />
  <path d="M-8,-25 L8,-5 L-2,-5 L8,25 L-8,5 L2,5 Z" fill="url(#grad_accent)" />
</g>
"""
call_mcp("add_raw_svg", {"svg": logo_svg})

call_mcp("add_text", {"x": 272, "y": 410, "text": "SoftCom", "font_size": 42, "fill": "#ffffff", "text_anchor": "middle"})
call_mcp("add_text", {"x": 272, "y": 455, "text": "ENERGY MANAGEMENT", "font_size": 18, "fill": "rgba(255,255,255,0.6)", "text_anchor": "middle"})

# 4. SECCIÓN 2: SERVICES
call_mcp("add_rect", {"x": 544, "y": 0, "width": 544, "height": 1056, "fill": "#f8f9fa"})
call_mcp("add_text", {"x": 816, "y": 115, "text": "Soluciones Integradas", "font_size": 28, "fill": "#1a1a2e", "text_anchor": "middle"})

# Una tarjeta de ejemplo vía MCP
call_mcp("add_rect", {"x": 584, "y": 170, "width": 464, "height": 115, "fill": "url(#grad_card)", "rx": 12})
call_mcp("add_text", {"x": 694, "y": 212, "text": "Gestión de Activos", "font_size": 16, "fill": "#1a1a2e"})

# 5. SECCIÓN 3: TECH
call_mcp("add_rect", {"x": 1088, "y": 0, "width": 544, "height": 1056, "fill": "#764ba2"})
call_mcp("add_text", {"x": 1360, "y": 115, "text": "Stack de Vanguardia", "font_size": 28, "fill": "#ffffff", "text_anchor": "middle"})

# 6. Guardar y mostrar
filename = "brochure_mcp_output.svg"
call_mcp("save", {"filename": filename})
print(f"Diseño guardado en el workspace del MCP como {filename}")

# Abrir en Inkscape
call_mcp("open_in_inkscape", {})
print("Abriendo resultado en Inkscape...")
