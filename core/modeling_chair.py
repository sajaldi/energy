import bpy
import math

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

def create_material(name, color, roughness=0.5, specular=0.5, alpha=1.0):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    bsdf.inputs['Base Color'].default_value = color
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Specular IOR Level'].default_value = specular
    
    if alpha < 1.0:
        mat.blend_method = 'BLEND'
        bsdf.inputs['Alpha'].default_value = alpha
        
    return mat

def create_chair():
    clear_scene()
    
    # Materials
    m_black_plastic = create_material("BlackPlastic", (0.02, 0.02, 0.02, 1), roughness=0.3)
    m_black_fabric = create_material("BlackFabric", (0.05, 0.05, 0.05, 1), roughness=0.9)
    m_gray_mesh = create_material("GrayMesh", (0.4, 0.4, 0.4, 0.6), roughness=0.5, alpha=0.6)
    m_metal = create_material("Metal", (0.8, 0.8, 0.8, 1), roughness=0.1, specular=1.0)
    
    # --- 1. Base (5-star) ---
    hub_radius = 0.05
    arm_length = 0.35
    for i in range(5):
        angle = math.radians(i * 360 / 5)
        # Arm
        bpy.ops.mesh.primitive_cube_add(size=1)
        arm = bpy.context.active_object
        arm.name = f"BaseArm_{i}"
        arm.scale = (arm_length, 0.03, 0.02)
        arm.location = (math.cos(angle) * (arm_length/2 + hub_radius), math.sin(angle) * (arm_length/2 + hub_radius), 0.1)
        arm.rotation_euler[2] = angle
        arm.data.materials.append(m_black_plastic)
        
        # Caster
        bpy.ops.mesh.primitive_cylinder_add(radius=0.03, depth=0.05)
        caster = bpy.context.active_object
        caster.name = f"Caster_{i}"
        caster.location = (math.cos(angle) * (arm_length + hub_radius), math.sin(angle) * (arm_length + hub_radius), 0.03)
        caster.rotation_euler[0] = math.radians(90)
        caster.rotation_euler[1] = angle
        caster.data.materials.append(m_black_plastic)

    # Central Hub
    bpy.ops.mesh.primitive_cylinder_add(radius=hub_radius+0.02, depth=0.1)
    hub = bpy.context.active_object
    hub.location = (0, 0, 0.1)
    hub.data.materials.append(m_black_plastic)

    # --- 2. Gas Lift ---
    bpy.ops.mesh.primitive_cylinder_add(radius=0.03, depth=0.3)
    lift = bpy.context.active_object
    lift.location = (0, 0, 0.25)
    lift.data.materials.append(m_metal)

    # --- 3. Seat ---
    bpy.ops.mesh.primitive_cube_add(size=1)
    seat = bpy.context.active_object
    seat.name = "Seat"
    seat.scale = (0.5, 0.48, 0.08)
    seat.location = (0, -0.05, 0.45)
    seat.data.materials.append(m_black_fabric)
    
    # Seat Substructure
    bpy.ops.mesh.primitive_cube_add(size=1)
    sub = bpy.context.active_object
    sub.scale = (0.45, 0.4, 0.05)
    sub.location = (0, -0.05, 0.4)
    sub.data.materials.append(m_black_plastic)

    # --- 4. Backrest Frame ---
    # Simplified frame as a curve or flattened cube
    bpy.ops.mesh.primitive_cube_add(size=1)
    b_frame = bpy.context.active_object
    b_frame.scale = (0.45, 0.03, 0.6)
    b_frame.location = (0, 0.35, 0.8)
    b_frame.data.materials.append(m_black_plastic)
    
    # Mesh inward
    bpy.ops.mesh.primitive_plane_add(size=1)
    mesh = bpy.context.active_object
    mesh.scale = (0.42, 0.58, 1)
    mesh.location = (0, 0.355, 0.8)
    mesh.rotation_euler[0] = math.radians(90)
    mesh.data.materials.append(m_gray_mesh)

    # --- 5. Armrests ---
    for side in [-1, 1]:
        # Arm post
        bpy.ops.mesh.primitive_cube_add(size=1)
        post = bpy.context.active_object
        post.scale = (0.04, 0.04, 0.25)
        post.location = (0.28 * side, 0, 0.6)
        post.data.materials.append(m_black_plastic)
        
        # Arm pad
        bpy.ops.mesh.primitive_cube_add(size=1)
        pad = bpy.context.active_object
        pad.scale = (0.08, 0.25, 0.03)
        pad.location = (0.28 * side, 0, 0.73)
        pad.data.materials.append(m_black_plastic)

    # Add a floor for context
    bpy.ops.mesh.primitive_plane_add(size=10)
    floor = bpy.context.active_object
    floor.location = (0, 0, 0)
    m_floor = create_material("Floor", (1, 1, 1, 1), roughness=0.1)
    floor.data.materials.append(m_floor)

    # Lights
    bpy.ops.object.light_add(type='AREA', location=(2, -2, 3))
    light = bpy.context.active_object
    light.data.energy = 1000
    
    # Camera
    bpy.ops.object.camera_add(location=(1.5, -1.5, 1.2), rotation=(math.radians(70), 0, math.radians(45)))
    cam = bpy.context.active_object
    bpy.context.scene.camera = cam

    # Render settings
    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.render.resolution_x = 1024
    bpy.context.scene.render.resolution_y = 1024
    bpy.context.scene.cycles.samples = 128
    
    # Render and save
    bpy.context.scene.render.filepath = os.path.abspath("chair_preview.png")
    bpy.ops.render.render(write_still=True)

if __name__ == "__main__":
    import os
    create_chair()
