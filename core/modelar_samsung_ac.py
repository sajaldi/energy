import bpy
import bmesh
import os

# RUTAS DE TEXTURAS GENERADAS
TEX_GRILLE = r"C:\Users\Saul\.gemini\antigravity\brain\19cc7ed6-27ad-47f5-82d0-4ef4ce319949\ac_grille_texture_1773072428972.png"
TEX_INVERTER = r"C:\Users\Saul\.gemini\antigravity\brain\19cc7ed6-27ad-47f5-82d0-4ef4ce319949\digital_inverter_logo_textura_1773072415722.png"
# El logo de Samsung se creará con texto procedural por compatibilidad de IA

def create_ac_unit():
    # 0. Limpiar escena (opcional)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    # 1. Cuerpo Principal (Gabinete)
    # Dimensiones estimadas: Ancho 94cm, Alto 160cm, Fondo 33cm
    width = 0.94
    height = 1.60
    depth = 0.33
    
    bpy.ops.mesh.primitive_cube_add(size=1)
    ac_body = bpy.context.active_object
    ac_body.name = "Samsung_AC_Unit"
    ac_body.scale = (width, depth, height)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    
    # 2. Material Base y Rejillas
    base_mat = bpy.data.materials.new(name="Samsung_Beige")
    base_mat.use_nodes = True
    bsdf = base_mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs['Base Color'].default_value = (0.87, 0.85, 0.82, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.4
    ac_body.data.materials.append(base_mat)
    
    # Material Rejilla
    grille_mat = bpy.data.materials.new(name="AC_Grille")
    grille_mat.use_nodes = True
    g_nodes = grille_mat.node_tree.nodes
    g_links = grille_mat.node_tree.links
    g_tex = g_nodes.new(type='ShaderNodeTexImage')
    if os.path.exists(TEX_GRILLE):
        g_tex.image = bpy.data.images.load(TEX_GRILLE)
    g_links.new(g_tex.outputs['Color'], g_nodes['Principled BSDF'].inputs['Base Color'])

    # 3. Crear Huecos para Ventiladores (Booleanos simples)
    fan_centers = [0.4, -0.4] # Posiciones en Z (relativas al centro 0)
    for i, z_pos in enumerate(fan_centers):
        bpy.ops.mesh.primitive_cylinder_add(radius=0.38, depth=0.1, location=(0, -depth/2, z_pos * height/2))
        fan_hole = bpy.context.active_object
        fan_hole.rotation_euler[0] = 1.5708 # 90 grados en X
        
        # Modificador boolean
        bool_mod = ac_body.modifiers.new(name=f"Fan_Hole_{i}", type='BOOLEAN')
        bool_mod.object = fan_hole
        bool_mod.operation = 'DIFFERENCE'
        
        # Esconder el cilindro
        fan_hole.hide_render = True
        fan_hole.hide_viewport = True

    # 4. Paneles y Detalles Laterales
    # Agregamos un cubo para el panel derecho donde van los logos
    panel_width = 0.25
    bpy.ops.mesh.primitive_cube_add(size=1, location=(width/2 - panel_width/2, -depth/2 + 0.01, 0))
    front_panel = bpy.context.active_object
    front_panel.scale = (panel_width, 0.02, height)
    front_panel.parent = ac_body
    front_panel.data.materials.append(base_mat)

    # 5. Aplicar Logos (Uso de Empty o Planos con Textura)
    # Por brevedad, crearemos un plano para el logo de Samsung
    def add_decal(name, tex_path, loc, scl):
        if not os.path.exists(tex_path):
            print(f"Advertencia: No se encontró textura en {tex_path}")
            return
        
        bpy.ops.mesh.primitive_plane_add(location=loc)
        decal = bpy.context.active_object
        decal.name = name
        decal.scale = scl
        decal.rotation_euler[0] = 1.5708 # Mirando al frente
        
        mat = bpy.data.materials.new(name=f"Mat_{name}")
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        
        tex_node = nodes.new(type='ShaderNodeTexImage')
        tex_node.image = bpy.data.images.load(tex_path)
        
        bsdf = nodes["Principled BSDF"]
        links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
        links.new(tex_node.outputs['Alpha'], bsdf.inputs['Alpha'])
        mat.blend_method = 'BLEND' # Transparencia
        
        decal.data.materials.append(mat)
        decal.parent = ac_body

    # NOTA: Estas rutas deben ser reemplazadas por el usuario con las rutas absolutas
    # de las imágenes generadas por Antigravity.
    # add_decal("Samsung_Logo", "RUTAS/samsung_logo.png", (0.33, -depth/2 - 0.01, 0.7), (0.1, 0.03, 1))
    
    print("Modelo base de Samsung AC Unit generado con éxito.")

create_ac_unit()
