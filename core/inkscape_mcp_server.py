"""
Inkscape MCP Server - Model Context Protocol Bridge for Inkscape
================================================================
Un servidor HTTP que permite a un agente de IA (Antigravity) controlar Inkscape
y manipular archivos SVG de forma programática.

Modo de uso:
  python inkscape_mcp_server.py [--port 8013] [--inkscape-path "C:/Program Files/Inkscape/bin/inkscape.exe"]

Capacidades:
  1. Crear/editar SVGs programáticamente (sin requerir Inkscape)
  2. Ejecutar acciones de Inkscape (CLI --actions)
  3. Exportar SVG a PNG/PDF (requiere Inkscape instalado)
  4. Modo shell interactivo de Inkscape

Protocolo HTTP:
  POST / → JSON con { "action": "...", "params": {...} }
"""

import json
import os
import sys
import signal
import subprocess
import tempfile
import threading
import time
import base64
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# ===== CONFIGURACIÓN =====
DEFAULT_PORT = 8013
INKSCAPE_PATH = None  # Se detecta automáticamente o se pasa como argumento

# Canvas por defecto (A4 en px a 96 DPI)
DEFAULT_WIDTH = 793.7  # 210mm
DEFAULT_HEIGHT = 1122.5  # 297mm

# ===== SVG BUILDER =====
# Manipulación directa de SVG sin requerir Inkscape

class SVGDocument:
    """Generador y manipulador de documentos SVG."""
    
    SVG_NS = "http://www.w3.org/2000/svg"
    XLINK_NS = "http://www.w3.org/1999/xlink"
    INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"
    
    def __init__(self, width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT, units="px"):
        self.width = width
        self.height = height
        self.units = units
        self.elements = []
        self.defs = []
        self.layers = {}
        self._id_counter = 0
    
    def _next_id(self, prefix="elem"):
        self._id_counter += 1
        return f"{prefix}_{self._id_counter}"
    
    def add_rect(self, x, y, width, height, fill="#000000", stroke="none", 
                 stroke_width=1, rx=0, ry=0, opacity=1, layer=None, id=None):
        elem_id = id or self._next_id("rect")
        elem = (f'<rect id="{elem_id}" x="{x}" y="{y}" width="{width}" height="{height}" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}" '
                f'rx="{rx}" ry="{ry}" opacity="{opacity}" />')
        self._add_element(elem, layer)
        return elem_id
    
    def add_circle(self, cx, cy, r, fill="#000000", stroke="none", 
                   stroke_width=1, opacity=1, layer=None, id=None):
        elem_id = id or self._next_id("circle")
        elem = (f'<circle id="{elem_id}" cx="{cx}" cy="{cy}" r="{r}" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}" '
                f'opacity="{opacity}" />')
        self._add_element(elem, layer)
        return elem_id
    
    def add_ellipse(self, cx, cy, rx, ry, fill="#000000", stroke="none",
                    stroke_width=1, opacity=1, layer=None, id=None):
        elem_id = id or self._next_id("ellipse")
        elem = (f'<ellipse id="{elem_id}" cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}" '
                f'opacity="{opacity}" />')
        self._add_element(elem, layer)
        return elem_id
    
    def add_line(self, x1, y1, x2, y2, stroke="#000000", stroke_width=2,
                 stroke_linecap="round", opacity=1, layer=None, id=None):
        elem_id = id or self._next_id("line")
        elem = (f'<line id="{elem_id}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                f'stroke="{stroke}" stroke-width="{stroke_width}" '
                f'stroke-linecap="{stroke_linecap}" opacity="{opacity}" />')
        self._add_element(elem, layer)
        return elem_id
    
    def add_polyline(self, points, stroke="#000000", fill="none", stroke_width=2,
                     stroke_linejoin="round", opacity=1, layer=None, id=None):
        elem_id = id or self._next_id("polyline")
        pts_str = " ".join(f"{x},{y}" for x, y in points)
        elem = (f'<polyline id="{elem_id}" points="{pts_str}" '
                f'stroke="{stroke}" fill="{fill}" stroke-width="{stroke_width}" '
                f'stroke-linejoin="{stroke_linejoin}" opacity="{opacity}" />')
        self._add_element(elem, layer)
        return elem_id
    
    def add_polygon(self, points, fill="#000000", stroke="none", stroke_width=1,
                    opacity=1, layer=None, id=None):
        elem_id = id or self._next_id("polygon")
        pts_str = " ".join(f"{x},{y}" for x, y in points)
        elem = (f'<polygon id="{elem_id}" points="{pts_str}" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}" '
                f'opacity="{opacity}" />')
        self._add_element(elem, layer)
        return elem_id
    
    def add_path(self, d, fill="none", stroke="#000000", stroke_width=2,
                 opacity=1, layer=None, id=None):
        elem_id = id or self._next_id("path")
        elem = (f'<path id="{elem_id}" d="{d}" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}" '
                f'opacity="{opacity}" />')
        self._add_element(elem, layer)
        return elem_id
    
    def add_text(self, x, y, text, font_size=16, font_family="Arial",
                 fill="#000000", font_weight="normal", text_anchor="start",
                 opacity=1, layer=None, id=None):
        elem_id = id or self._next_id("text")
        # Escapar caracteres especiales en XML
        safe_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        elem = (f'<text id="{elem_id}" x="{x}" y="{y}" '
                f'font-size="{font_size}" font-family="{font_family}" '
                f'fill="{fill}" font-weight="{font_weight}" text-anchor="{text_anchor}" '
                f'opacity="{opacity}">{safe_text}</text>')
        self._add_element(elem, layer)
        return elem_id
    
    def add_image(self, x, y, width, height, href, layer=None, id=None):
        elem_id = id or self._next_id("image")
        elem = (f'<image id="{elem_id}" x="{x}" y="{y}" width="{width}" height="{height}" '
                f'href="{href}" />')
        self._add_element(elem, layer)
        return elem_id
    
    def add_group(self, transform="", layer=None, id=None):
        """Retorna un group_id que puede usarse como 'layer' en otros elementos."""
        elem_id = id or self._next_id("group")
        self.layers[elem_id] = {"transform": transform, "elements": []}
        return elem_id
    
    def add_gradient(self, gradient_id, type="linear", x1="0%", y1="0%", 
                     x2="100%", y2="0%", stops=None):
        """Agrega un gradiente a los defs del SVG."""
        if stops is None:
            stops = [("0%", "#000000", 1), ("100%", "#ffffff", 1)]
        
        stops_svg = ""
        for offset, color, opacity in stops:
            stops_svg += f'<stop offset="{offset}" stop-color="{color}" stop-opacity="{opacity}" />'
        
        if type == "linear":
            grad = (f'<linearGradient id="{gradient_id}" x1="{x1}" y1="{y1}" '
                    f'x2="{x2}" y2="{y2}">{stops_svg}</linearGradient>')
        else:
            grad = (f'<radialGradient id="{gradient_id}" cx="{x1}" cy="{y1}" '
                    f'r="{x2}">{stops_svg}</radialGradient>')
        
        self.defs.append(grad)
        return gradient_id
    
    def add_filter(self, filter_id, filter_xml):
        """Agrega un filtro SVG personalizado."""
        self.defs.append(f'<filter id="{filter_id}">{filter_xml}</filter>')
        return filter_id
    
    def add_raw_svg(self, svg_string, layer=None):
        """Agrega SVG crudo directamente al documento."""
        self._add_element(svg_string, layer)
    
    def _add_element(self, elem, layer=None):
        if layer and layer in self.layers:
            self.layers[layer]["elements"].append(elem)
        else:
            self.elements.append(elem)
    
    def render(self):
        """Genera el SVG completo como string."""
        svg = f'''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="{self.SVG_NS}" 
     xmlns:xlink="{self.XLINK_NS}"
     xmlns:inkscape="{self.INKSCAPE_NS}"
     width="{self.width}{self.units}" 
     height="{self.height}{self.units}"
     viewBox="0 0 {self.width} {self.height}">
'''
        # Defs
        if self.defs:
            svg += "  <defs>\n"
            for d in self.defs:
                svg += f"    {d}\n"
            svg += "  </defs>\n"
        
        # Elementos sueltos
        for elem in self.elements:
            svg += f"  {elem}\n"
        
        # Grupos/Layers
        for layer_id, layer_data in self.layers.items():
            transform = f' transform="{layer_data["transform"]}"' if layer_data["transform"] else ""
            svg += f'  <g id="{layer_id}"{transform}>\n'
            for elem in layer_data["elements"]:
                svg += f"    {elem}\n"
            svg += "  </g>\n"
        
        svg += "</svg>"
        return svg
    
    def save(self, filepath):
        """Guarda el SVG en un archivo."""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.render())
        return filepath


# ===== INKSCAPE CLI WRAPPER =====

class InkscapeCLI:
    """Wrapper para el CLI de Inkscape."""
    
    def __init__(self, inkscape_path=None):
        self.inkscape_path = inkscape_path or self._find_inkscape()
        self.available = self.inkscape_path is not None
        if self.available:
            print(f"[MCP-Inkscape] Inkscape encontrado: {self.inkscape_path}")
        else:
            print("[MCP-Inkscape] Inkscape NO encontrado. Solo funciones SVG directas disponibles.")
    
    def _find_inkscape(self):
        """Busca Inkscape en ubicaciones comunes."""
        search_paths = [
            r"C:\Windows.old\Program Files\Inkscape\bin\inkscape.exe",
            r"C:\Program Files\Inkscape\bin\inkscape.exe",
            r"C:\Program Files (x86)\Inkscape\bin\inkscape.exe",
            r"C:\Program Files\Inkscape\inkscape.exe",
            r"D:\Inkscape\bin\inkscape.exe",
            r"D:\Program Files\Inkscape\bin\inkscape.exe",
        ]
        for p in search_paths:
            if os.path.exists(p):
                return p
        
        # Intentar encontrar en PATH
        try:
            result = subprocess.run(["where", "inkscape"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return result.stdout.strip().split("\n")[0]
        except:
            pass
        
        return None
    
    def version(self):
        """Obtiene la versión de Inkscape."""
        if not self.available:
            return {"error": "Inkscape no disponible"}
        try:
            result = subprocess.run(
                [self.inkscape_path, "--version"],
                capture_output=True, text=True, timeout=10
            )
            return {"version": result.stdout.strip()}
        except Exception as e:
            return {"error": str(e)}
    
    def export_png(self, svg_path, output_path, width=None, height=None, dpi=96):
        """Exporta un SVG a PNG usando Inkscape."""
        if not self.available:
            return {"error": "Inkscape no disponible para exportar"}
        
        cmd = [self.inkscape_path, svg_path, "--export-filename", output_path]
        if width:
            cmd.extend(["--export-width", str(width)])
        if height:
            cmd.extend(["--export-height", str(height)])
        cmd.extend(["--export-dpi", str(dpi)])
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if os.path.exists(output_path):
                return {"status": "success", "path": output_path}
            else:
                return {"error": f"Export failed: {result.stderr}"}
        except Exception as e:
            return {"error": str(e)}
    
    def export_pdf(self, svg_path, output_path):
        """Exporta un SVG a PDF usando Inkscape."""
        if not self.available:
            return {"error": "Inkscape no disponible para exportar"}
        
        cmd = [self.inkscape_path, svg_path, "--export-filename", output_path,
               "--export-type", "pdf"]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if os.path.exists(output_path):
                return {"status": "success", "path": output_path}
            else:
                return {"error": f"Export failed: {result.stderr}"}
        except Exception as e:
            return {"error": str(e)}
    
    def run_actions(self, svg_path, actions):
        """Ejecuta acciones de Inkscape (--actions)."""
        if not self.available:
            return {"error": "Inkscape no disponible"}
        
        cmd = [self.inkscape_path, svg_path, "--actions", actions]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            return {
                "status": "success",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        except Exception as e:
            return {"error": str(e)}
    
    def open_gui(self, svg_path=None):
        """Abre Inkscape con la GUI (no bloquea)."""
        if not self.available:
            return {"error": "Inkscape no disponible"}
        
        cmd = [self.inkscape_path]
        if svg_path:
            cmd.append(svg_path)
        
        try:
            subprocess.Popen(cmd)
            return {"status": "success", "message": "Inkscape abierto"}
        except Exception as e:
            return {"error": str(e)}


# ===== HTTP HANDLER =====

# Estado global
current_doc = SVGDocument()
inkscape = InkscapeCLI(INKSCAPE_PATH)
workspace_dir = tempfile.mkdtemp(prefix="inkscape_mcp_")


class InkscapeMCPHandler(BaseHTTPRequestHandler):
    """Handler HTTP para el MCP de Inkscape."""
    
    def log_message(self, format, *args):
        print(f"[MCP-Inkscape] {format % args}")
    
    def do_GET(self):
        """GET / → Info del servidor."""
        info = {
            "name": "Inkscape MCP Server",
            "version": "1.0.0",
            "inkscape_available": inkscape.available,
            "inkscape_version": inkscape.version() if inkscape.available else None,
            "workspace": workspace_dir,
            "canvas": {
                "width": current_doc.width,
                "height": current_doc.height,
                "elements": len(current_doc.elements),
                "layers": len(current_doc.layers)
            },
            "actions": [
                "new_document", "add_rect", "add_circle", "add_ellipse",
                "add_line", "add_polyline", "add_polygon", "add_path",
                "add_text", "add_image", "add_group", "add_gradient",
                "add_raw_svg", "render", "save", "export_png", "export_pdf",
                "open_in_inkscape", "inkscape_actions", "get_svg"
            ]
        }
        self._send_json(200, info)
    
    def do_POST(self):
        """POST / → Ejecutar acción."""
        global current_doc
        
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body) if body else {}
            
            action = data.get("action", "")
            params = data.get("params", {})
            
            result = self._handle_action(action, params)
            self._send_json(200, {"status": "success", "result": result})
            
        except Exception as e:
            import traceback
            self._send_json(500, {
                "status": "error", 
                "error": str(e),
                "traceback": traceback.format_exc()
            })
    
    def _handle_action(self, action, params):
        global current_doc
        
        # === Documento ===
        if action == "new_document":
            current_doc = SVGDocument(
                width=params.get("width", DEFAULT_WIDTH),
                height=params.get("height", DEFAULT_HEIGHT),
                units=params.get("units", "px")
            )
            return {"message": f"Nuevo documento {current_doc.width}x{current_doc.height}{current_doc.units}"}
        
        # === Formas ===
        elif action == "add_rect":
            elem_id = current_doc.add_rect(**params)
            return {"id": elem_id}
        
        elif action == "add_circle":
            elem_id = current_doc.add_circle(**params)
            return {"id": elem_id}
        
        elif action == "add_ellipse":
            elem_id = current_doc.add_ellipse(**params)
            return {"id": elem_id}
        
        elif action == "add_line":
            elem_id = current_doc.add_line(**params)
            return {"id": elem_id}
        
        elif action == "add_polyline":
            elem_id = current_doc.add_polyline(**params)
            return {"id": elem_id}
        
        elif action == "add_polygon":
            elem_id = current_doc.add_polygon(**params)
            return {"id": elem_id}
        
        elif action == "add_path":
            elem_id = current_doc.add_path(**params)
            return {"id": elem_id}
        
        elif action == "add_text":
            elem_id = current_doc.add_text(**params)
            return {"id": elem_id}
        
        elif action == "add_image":
            elem_id = current_doc.add_image(**params)
            return {"id": elem_id}
        
        # === Estructura ===
        elif action == "add_group":
            group_id = current_doc.add_group(**params)
            return {"id": group_id}
        
        elif action == "add_gradient":
            grad_id = current_doc.add_gradient(**params)
            return {"id": grad_id}
        
        elif action == "add_raw_svg":
            current_doc.add_raw_svg(params.get("svg", ""), params.get("layer"))
            return {"message": "SVG crudo agregado"}
        
        # === Exportación ===
        elif action == "get_svg":
            return {"svg": current_doc.render()}
        
        elif action == "render":
            return {"svg": current_doc.render(), "elements": len(current_doc.elements)}
        
        elif action == "save":
            filename = params.get("filename", "output.svg")
            filepath = os.path.join(workspace_dir, filename)
            current_doc.save(filepath)
            return {"path": filepath}
        
        elif action == "export_png":
            svg_path = params.get("svg_path")
            if not svg_path:
                svg_path = os.path.join(workspace_dir, "_temp_export.svg")
                current_doc.save(svg_path)
            
            output_path = params.get("output_path", 
                                     os.path.join(workspace_dir, "export.png"))
            result = inkscape.export_png(
                svg_path, output_path,
                width=params.get("width"),
                height=params.get("height"),
                dpi=params.get("dpi", 96)
            )
            return result
        
        elif action == "export_pdf":
            svg_path = params.get("svg_path")
            if not svg_path:
                svg_path = os.path.join(workspace_dir, "_temp_export.svg")
                current_doc.save(svg_path)
            
            output_path = params.get("output_path",
                                     os.path.join(workspace_dir, "export.pdf"))
            result = inkscape.export_pdf(svg_path, output_path)
            return result
        
        # === Inkscape directo ===
        elif action == "open_in_inkscape":
            svg_path = params.get("svg_path")
            if not svg_path:
                svg_path = os.path.join(workspace_dir, "_inkscape_open.svg")
                current_doc.save(svg_path)
            return inkscape.open_gui(svg_path)
        
        elif action == "inkscape_actions":
            svg_path = params.get("svg_path")
            if not svg_path:
                svg_path = os.path.join(workspace_dir, "_inkscape_actions.svg")
                current_doc.save(svg_path)
            return inkscape.run_actions(svg_path, params.get("actions", ""))
        
        elif action == "inkscape_version":
            return inkscape.version()
        
        # === Utilidades ===  
        elif action == "list_files":
            files = os.listdir(workspace_dir)
            return {"workspace": workspace_dir, "files": files}
        
        elif action == "read_file":
            filepath = params.get("path", "")
            if not os.path.isabs(filepath):
                filepath = os.path.join(workspace_dir, filepath)
            with open(filepath, "r", encoding="utf-8") as f:
                return {"content": f.read(), "path": filepath}
        
        elif action == "load_svg":
            filepath = params.get("path", "")
            if not os.path.isabs(filepath):
                filepath = os.path.join(workspace_dir, filepath)
            with open(filepath, "r", encoding="utf-8") as f:
                svg_content = f.read()
            # No parseamos, pero podemos agregar como raw
            current_doc = SVGDocument(
                width=params.get("width", DEFAULT_WIDTH),
                height=params.get("height", DEFAULT_HEIGHT)
            )
            return {"message": f"Documento cargado desde {filepath}", "path": filepath}
        
        else:
            return {"error": f"Acción desconocida: '{action}'"}
    
    def _send_json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))
    
    def do_OPTIONS(self):
        """CORS preflight."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


# ===== MAIN =====

def main():
    global INKSCAPE_PATH
    
    port = DEFAULT_PORT
    
    # Parsear argumentos simples
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--port" and i + 1 < len(args):
            port = int(args[i + 1])
        elif arg == "--inkscape-path" and i + 1 < len(args):
            INKSCAPE_PATH = args[i + 1]
    
    if INKSCAPE_PATH:
        global inkscape
        inkscape = InkscapeCLI(INKSCAPE_PATH)
    
    server = HTTPServer(("localhost", port), InkscapeMCPHandler)
    
    print("=" * 60)
    print(f"  Inkscape MCP Server v1.0")
    print(f"  Escuchando en: http://localhost:{port}")
    print(f"  Workspace: {workspace_dir}")
    print(f"  Inkscape: {'OK ' + str(inkscape.inkscape_path) if inkscape.available else 'NO ENCONTRADO'}")
    print("=" * 60)
    print(f"  Ejemplo de uso:")
    print(f'  curl -X POST http://localhost:{port} -d \'{{"action":"add_rect","params":{{"x":10,"y":10,"width":100,"height":50,"fill":"#3498db"}}}}\'')
    print("=" * 60)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[MCP-Inkscape] Servidor detenido.")
        server.shutdown()


if __name__ == "__main__":
    main()
