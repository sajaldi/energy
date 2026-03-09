import bpy
import math

# ELIMINACIÓN TOTAL DE OBJETOS PREVIOS (Excepto el Filtro)
for obj in list(bpy.data.objects):
    if "Body" not in obj.name and "Lid" not in obj.name and "Clamp" not in obj.name:
         bpy.data.objects.remove(obj, do_unlink=True)

def create_mat(name, color, emit=0):
    if name in bpy.data.materials:
        mat = bpy.data.materials[name]
    else:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs["Base Color"].default_value = color
    if emit > 0:
        bsdf.inputs["Emission Strength"].default_value = emit
        bsdf.inputs["Emission Color"].default_value = color
    out = nodes.new('ShaderNodeOutputMaterial')
    mat.node_tree.links.new(bsdf.outputs[0], out.inputs[0])
    mat.diffuse_color = color
    return mat

# Materiales Industriales
m_panel = create_mat("M_Panel", (0.8, 0.8, 0.8, 1))
m_black = create_mat("M_Black", (0.04, 0.04, 0.04, 1))
m_red = create_mat("M_Red", (0.8, 0.02, 0.02, 1))
m_red_L = create_mat("M_Red_L", (1, 0.2, 0.2, 1), 6)
m_green = create_mat("M_Green", (0.02, 0.7, 0.02, 1))
m_green_L = create_mat("M_Green_L", (0.2, 1, 0.2, 1), 5)
m_orange = create_mat("M_Orange", (1, 0.5, 0, 1))
m_blue = create_mat("M_Blue", (0, 0.3, 1, 1))
m_screen = create_mat("M_Screen", (0.01, 0.01, 0.01, 1))
m_sticker = create_mat("M_Sticker", (0.9, 0.85, 0, 1))

# Gabinete (Dimensiones reales según la foto)
W, D, H = 0.65, 0.35, 1.95
bpy.ops.mesh.primitive_cube_add(size=1, location=(0,0, H/2))
cabinet = bpy.context.object
cabinet.name = "Elec_Panel_Body"
cabinet.scale = (W, D, H)
cabinet.data.materials.append(m_panel)

# Zócalo negro
bpy.ops.mesh.primitive_cube_add(size=1, location=(0,0, 0.05))
base = bpy.context.object
base.scale = (W+0.02, D+0.02, 0.1)
base.data.materials.append(m_black)

Y_FRONT = D/2 + 0.005

# 1. HMI (Pantalla Rectangular)
# Marco
bpy.ops.mesh.primitive_cube_add(size=1, location=(0.04, Y_FRONT + 0.01, 1.55))
hmi_f = bpy.context.object
hmi_f.scale = (0.28, 0.02, 0.38)
hmi_f.data.materials.append(m_black)
# Pantalla
bpy.ops.mesh.primitive_cube_add(size=1, location=(0.04, Y_FRONT + 0.015, 1.55))
hmi_s = bpy.context.object
hmi_s.scale = (0.22, 0.015, 0.3)
hmi_s.data.materials.append(m_screen)

# 2. Mandos de Control
# Naranja y Azul
bpy.ops.mesh.primitive_cylinder_add(radius=0.025, depth=0.04, location=(-0.06, Y_FRONT + 0.02, 1.32))
btn_o = bpy.context.object
btn_o.rotation_euler[0] = math.radians(90)
btn_o.data.materials.append(m_orange)

bpy.ops.mesh.primitive_cylinder_add(radius=0.025, depth=0.04, location=(0.14, Y_FRONT + 0.02, 1.32))
btn_b = bpy.context.object
btn_b.rotation_euler[0] = math.radians(90)
btn_b.data.materials.append(m_blue)

# Selector central
bpy.ops.mesh.primitive_cylinder_add(radius=0.02, depth=0.06, location=(0.04, Y_FRONT + 0.02, 1.22))
sel_m = bpy.context.object
sel_m.rotation_euler[0] = math.radians(90)
sel_m.data.materials.append(m_black)

# Reset Verde
bpy.ops.mesh.primitive_cylinder_add(radius=0.02, depth=0.04, location=(0.04, Y_FRONT + 0.02, 1.12))
btn_g = bpy.context.object
btn_g.rotation_euler[0] = math.radians(90)
btn_g.data.materials.append(m_green)

# 3. MATRIZ DEFINITIVA
SX, SZ = -0.18, 1.02
DX, DZ = 0.11, 0.15

for row in range(3):
    for col in range(5):
        cx, cz = SX + col*DX, SZ - row*DZ
        
        # Base negra
        bpy.ops.mesh.primitive_cylinder_add(radius=0.028, depth=0.01, location=(cx, Y_FRONT + 0.005, cz))
        b_black = bpy.context.object
        b_black.rotation_euler[0] = math.radians(90)
        b_black.data.materials.append(m_black)
        
        # Color
        mat = m_black
        if row == 0: mat = m_green_L if col == 0 else m_green
        elif row == 1: mat = m_red_L if col == 2 else m_red
        
        bpy.ops.mesh.primitive_cylinder_add(radius=0.018, depth=0.03, location=(cx, Y_FRONT + 0.02, cz))
        b_color = bpy.context.object
        b_color.rotation_euler[0] = math.radians(90)
        b_color.data.materials.append(mat)
        if row == 2: b_color.scale[0] = 0.4 # Forma de selector

# 4. Otros detalles
# Sticker Danger
bpy.ops.mesh.primitive_plane_add(size=1, location=(-0.24, Y_FRONT + 0.002, 1.42))
st = bpy.context.object
st.rotation_euler[0] = math.radians(90)
st.scale = (0.12, 0.1, 1)
st.data.materials.append(m_sticker)

# Manija
bpy.ops.mesh.primitive_cube_add(size=1, location=(-W/2+0.02, Y_FRONT+0.02, 0.9))
handle = bpy.context.object
handle.scale = (0.02, 0.03, 0.5)
handle.data.materials.append(m_black)

print("Panel reconstruido desde cero con éxito")
