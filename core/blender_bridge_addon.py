bl_info = {
    "name": "Antigravity Blender Bridge",
    "blender": (4, 0, 0),
    "category": "System",
    "description": "Bridge for Antigravity AI to inspect and control Blender via MCP.",
    "author": "Antigravity Team",
    "version": (0, 1, 0),
}

import bpy
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import os

# Puerto por defecto para el puente
PORT = 8012

class BlenderHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode('utf-8')
        
        try:
            data = json.loads(post_data)
            action = data.get('action')
            
            if action == 'execute':
                code = data.get('code', '')
                # Ejecutar en el hilo principal de Blender
                result = self.run_in_main_thread(code)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'success', 'result': result}).encode())
            
            elif action == 'get_scene':
                scene_data = self.get_scene_info()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'success', 'scene': scene_data}).encode())
            
            elif action == 'screenshot':
                # Tomar una captura del viewport activo
                path = self.get_viewport_render()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'success', 'path': path}).encode())
                
            else:
                self.send_error(400, "Unknown action")
                
        except Exception as e:
            self.send_error(500, str(e))

    def run_in_main_thread(self, code):
        # Usamos app.timers para ejecutar en el hilo principal de forma segura
        output = []
        def execute():
            try:
                # Capturar stdout si es necesario, o solo ejecutar
                exec_globals = {"bpy": bpy, "context": bpy.context}
                exec(code, exec_globals)
                output.append("Executed successfully")
            except Exception as e:
                print(f"Bridge Execution Error: {e}")
                output.append(f"Error: {str(e)}")
            return None
        
        bpy.app.timers.register(execute)
        return "Command queued for execution"

    def get_viewport_render(self):
        # Guardar en tmp
        import tempfile
        tmp_dir = tempfile.gettempdir()
        path = os.path.join(tmp_dir, "blender_view.png")
        
        def do_render():
            try:
                # Asegurar que el viewport esté en modo Material Preview para ver colores
                for area in bpy.context.screen.areas:
                    if area.type == 'VIEW_3D':
                        for space in area.spaces:
                            if space.type == 'VIEW_3D':
                                space.shading.type = 'MATERIAL'
                                # Forzar luces y mundo
                                space.shading.use_scene_lights = True
                                space.shading.use_scene_world = True
                                # Fallback para modo Solid
                                space.shading.color_type = 'MATERIAL'
                
                # Cambiar el formato a PNG
                orig_format = bpy.context.scene.render.image_settings.file_format
                bpy.context.scene.render.image_settings.file_format = 'PNG'
                
                # Renderizar viewport activo
                bpy.ops.render.opengl(write_still=True)
                bpy.data.images['Render Result'].save_render(filepath=path)
                
                bpy.context.scene.render.image_settings.file_format = orig_format
            except Exception as e:
                print(f"Render error: {e}")
        
        bpy.app.timers.register(do_render)
        return path

    def get_scene_info(self):
        objects = []
        for obj in bpy.data.objects:
            objects.append({
                "name": obj.name,
                "type": obj.type,
                "location": list(obj.location),
                "rotation": list(obj.rotation_euler),
                "scale": list(obj.scale),
            })
        return {
            "objects": objects,
            "filename": bpy.data.filepath or "Untitled",
            "active_object": bpy.context.active_object.name if bpy.context.active_object else None
        }

server_thread = None
httpd = None

class BRIDGE_OT_start(bpy.types.Operator):
    bl_idname = "bridge.start"
    bl_label = "Start Bridge"
    
    def execute(self, context):
        global server_thread, httpd
        if server_thread and server_thread.is_alive():
            self.report({'INFO'}, "Bridge is already running")
            return {'CANCELLED'}
            
        def run_server():
            global httpd
            server_address = ('', PORT)
            httpd = HTTPServer(server_address, BlenderHandler)
            print(f"Blender Bridge listening on port {PORT}")
            httpd.serve_forever()

        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        self.report({'INFO'}, f"Bridge started on port {PORT}")
        return {'FINISHED'}

class BRIDGE_OT_stop(bpy.types.Operator):
    bl_idname = "bridge.stop"
    bl_label = "Stop Bridge"
    
    def execute(self, context):
        global httpd
        if httpd:
            httpd.shutdown()
            self.report({'INFO'}, "Bridge stopped")
        return {'FINISHED'}

class BRIDGE_PT_panel(bpy.types.Panel):
    bl_label = "Antigravity Bridge"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Bridge'
    
    def draw(self, context):
        layout = self.layout
        layout.operator("bridge.start")
        layout.operator("bridge.stop")

classes = (BRIDGE_OT_start, BRIDGE_OT_stop, BRIDGE_PT_panel)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
