import bpy
import math

# Limpiar escena
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

def create_metallic_material(name, color=(0.8, 0.8, 0.8, 1)):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs['Base Color'].default_value = color
        bsdf.inputs['Metallic'].default_value = 0.9
        bsdf.inputs['Roughness'].default_value = 0.2
    return mat

mat_metal = create_metallic_material("StainlessSteel")

# 1. Cuerpo Principal
bpy.ops.mesh.primitive_cylinder_add(radius=0.5, depth=2.5, location=(0, 0, 1.25))
body = bpy.context.object
body.name = "Body"
body.data.materials.append(mat_metal)

# 2. Tapa (Domo)
# Crear una esfera, cortarla y moverla arriba
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, location=(0, 0, 2.5))
lid = bpy.context.object
lid.name = "Lid"
lid.scale[2] = 0.4 # Aplanar un poco el domo
lid.data.materials.append(mat_metal)

# 3. Abrazadera / Clamp
bpy.ops.mesh.primitive_torus_add(major_radius=0.52, minor_radius=0.05, location=(0, 0, 2.5))
clamp = bpy.context.object
clamp.name = "Clamp"
clamp.data.materials.append(mat_metal)

# 4. Bridas Laterales (Entrada/Salida)
def add_flange(loc, rot_y):
    # Tubo
    bpy.ops.mesh.primitive_cylinder_add(radius=0.1, depth=0.4, location=loc)
    pipe = bpy.context.object
    pipe.rotation_euler[1] = math.radians(rot_y)
    pipe.data.materials.append(mat_metal)
    
    # Brida (Flange)
    flange_loc = list(loc)
    offset = 0.2 * (1 if loc[0] > 0 else -1)
    flange_loc[0] += offset
    bpy.ops.mesh.primitive_cylinder_add(radius=0.25, depth=0.04, location=flange_loc)
    flange = bpy.context.object
    flange.rotation_euler[1] = math.radians(rot_y)
    flange.data.materials.append(mat_metal)

# Entrada abajo
add_flange((0.5, 0, 0.8), 90)
# Salida arriba (lado opuesto o diferente altura)
add_flange((-0.5, 0, 1.7), 90)

# 5. Patas (4 patas en L)
def add_leg(angle_deg):
    angle = math.radians(angle_deg)
    x = math.cos(angle) * 0.4
    y = math.sin(angle) * 0.4
    
    # Parte vertical
    bpy.ops.mesh.primitive_cube_add(size=0.1, location=(x, y, -0.4))
    leg = bpy.context.object
    leg.scale[2] = 8.0 # Hacerla alta
    leg.location[2] = 0.2 # Ajustar base
    leg.data.materials.append(mat_metal)
    
    # Base de la pata (pie)
    bpy.ops.mesh.primitive_cube_add(size=0.15, location=(x*1.2, y*1.2, -0.2))
    foot = bpy.context.object
    foot.scale[2] = 0.1
    foot.data.materials.append(mat_metal)

for a in [45, 135, 225, 315]:
    add_leg(a)

# 6. Fitings pequeños frontales
bpy.ops.mesh.primitive_cylinder_add(radius=0.05, depth=0.1, location=(0.5, 0, 0.4))
f1 = bpy.context.object
f1.rotation_euler[1] = math.radians(90)
f1.data.materials.append(mat_metal)

bpy.ops.mesh.primitive_cylinder_add(radius=0.05, depth=0.1, location=(0.5, 0, 0.2))
f2 = bpy.context.object
f2.rotation_euler[1] = math.radians(90)
f2.data.materials.append(mat_metal)

# Unir todo para exportación fácil (opcional)
bpy.ops.object.select_all(action='SELECT')
# bpy.ops.object.join() # Mejor mantener separado por si quiere editar

# Suavizado
for obj in bpy.data.objects:
    if obj.type == 'MESH':
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.shade_smooth()

print("Filtro Pulidor creado exitosamente")
