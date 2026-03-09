import bpy
import math
import os

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

def apply_subdiv(obj, levels=2):
    subdiv = obj.modifiers.new(name="Subdivision", type='SUBSURF')
    subdiv.levels = levels
    subdiv.render_levels = levels
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.shade_smooth()

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
        # Arm (Curved)
        bpy.ops.mesh.primitive_cube_add(size=1)
        arm = bpy.context.active_object
        arm.name = f"BaseArm_{i}"
        arm.scale = (arm_length, 0.04, 0.02)
        arm.location = (math.cos(angle) * (arm_length/2 + hub_radius), math.sin(angle) * (arm_length/2 + hub_radius), 0.1)
        arm.rotation_euler[2] = angle
        arm.data.materials.append(m_black_plastic)
        apply_subdiv(arm, 1)
        
        # Caster
        bpy.ops.mesh.primitive_cylinder_add(radius=0.035, depth=0.04)
        caster = bpy.context.active_object
        caster.name = f"Caster_{i}"
        caster.location = (math.cos(angle) * (arm_length + hub_radius), math.sin(angle) * (arm_length + hub_radius), 0.035)
        caster.rotation_euler[0] = math.radians(90)
        caster.rotation_euler[1] = angle
        caster.data.materials.append(m_black_plastic)
        bpy.ops.object.shade_smooth()

    # Central Hub
    bpy.ops.mesh.primitive_cylinder_add(radius=hub_radius+0.02, depth=0.12)
    hub = bpy.context.active_object
    hub.location = (0, 0, 0.1)
    hub.data.materials.append(m_black_plastic)
    bpy.ops.object.shade_smooth()

    # --- 2. Gas Lift ---
    bpy.ops.mesh.primitive_cylinder_add(radius=0.03, depth=0.35)
    lift = bpy.context.active_object
    lift.location = (0, 0, 0.28)
    lift.data.materials.append(m_metal)
    bpy.ops.object.shade_smooth()

    # --- 3. Seat (Organic Shape) ---
    bpy.ops.mesh.primitive_cube_add(size=1)
    seat = bpy.context.active_object
    seat.name = "Seat"
    # Reshaping to be more organic
    seat.scale = (0.52, 0.5, 0.08)
    seat.location = (0, -0.05, 0.48)
    # Bevel for edges before subdiv
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    apply_subdiv(seat, 3)
    seat.data.materials.append(m_black_fabric)
    
    # Seat Substructure (Curved plastic)
    bpy.ops.mesh.primitive_cube_add(size=1)
    sub = bpy.context.active_object
    sub.scale = (0.48, 0.45, 0.12)
    sub.location = (0, -0.05, 0.42)
    apply_subdiv(sub, 2)
    sub.data.materials.append(m_black_plastic)

    # --- 4. Backrest Frame (Elegant Curve) ---
    # Outer Frame
    bpy.ops.mesh.primitive_cube_add(size=1)
    b_frame = bpy.context.active_object
    b_frame.name = "BackFrame"
    b_frame.scale = (0.46, 0.04, 0.62)
    b_frame.location = (0, 0.38, 0.85)
    # Slight tilt
    b_frame.rotation_euler[0] = math.radians(-10)
    apply_subdiv(b_frame, 2)
    b_frame.data.materials.append(m_black_plastic)
    
    # Mesh (Curved)
    bpy.ops.mesh.primitive_plane_add(size=1)
    mesh = bpy.context.active_object
    mesh.name = "BackMesh"
    mesh.scale = (0.44, 0.6, 1)
    mesh.location = (0, 0.39, 0.85)
    mesh.rotation_euler[0] = math.radians(80) # Follow frame tilt
    mesh.data.materials.append(m_gray_mesh)
    # Give mesh some thickness
    mod_solid = mesh.modifiers.new(name="Solidify", type='SOLIDIFY')
    mod_solid.thickness = 0.005

    # --- 5. Armrests (Sculpted) ---
    for side in [-1, 1]:
        # Arm post
        bpy.ops.mesh.primitive_cube_add(size=1)
        post = bpy.context.active_object
        post.scale = (0.03, 0.06, 0.22)
        post.location = (0.32 * side, -0.05, 0.6)
        apply_subdiv(post, 2)
        post.data.materials.append(m_black_plastic)
        
        # Arm pad (Ergonomic)
        bpy.ops.mesh.primitive_cube_add(size=1)
        pad = bpy.context.active_object
        pad.scale = (0.09, 0.28, 0.04)
        pad.location = (0.32 * side, -0.05, 0.74)
        apply_subdiv(pad, 3)
        pad.data.materials.append(m_black_plastic)

    # --- 6. Environmental Setup ---
    # Floor
    bpy.ops.mesh.primitive_plane_add(size=15)
    floor = bpy.context.active_object
    floor.location = (0, 0, 0)
    m_floor = create_material("Floor", (0.9, 0.9, 0.9, 1), roughness=0.2)
    floor.data.materials.append(m_floor)

    # Lights (Studio Setup)
    # Key Light
    bpy.ops.object.light_add(type='AREA', location=(3, -4, 4))
    key_light = bpy.context.active_object
    key_light.data.energy = 2000
    key_light.scale = (2, 2, 2)
    key_light.rotation_euler = (math.radians(45), 0, math.radians(45))

    # Fill Light
    bpy.ops.object.light_add(type='AREA', location=(-3, -2, 2))
    fill_light = bpy.context.active_object
    fill_light.data.energy = 800
    
    # Back Light
    bpy.ops.object.light_add(type='AREA', location=(0, 4, 3))
    back_light = bpy.context.active_object
    back_light.data.energy = 1200

    # Camera
    bpy.ops.object.camera_add(location=(1.8, -1.8, 1.4), rotation=(math.radians(70), 0, math.radians(45)))
    cam = bpy.context.active_object
    bpy.context.scene.camera = cam

    # Render settings
    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.render.resolution_x = 1024
    bpy.context.scene.render.resolution_y = 1024
    bpy.context.scene.cycles.samples = 256
    
    # Render and save
    bpy.context.scene.render.filepath = os.path.abspath("chair_preview_detailed.png")
    bpy.ops.render.render(write_still=True)

if __name__ == "__main__":
    create_chair()
