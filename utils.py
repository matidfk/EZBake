import bpy
import mathutils


class OBJECT_OT_ez_bake_overlay_setup(bpy.types.Operator):
    bl_idname = "object.ez_bake_overlay_setup"
    bl_options = {"INTERNAL"}
    bl_label = "Setup for baking an overlay layer"

    layer_index: bpy.props.IntProperty()

    def execute(self, context):
        original_object = context.object
        bpy.ops.object.select_all(action='DESELECT')

        # Join copies of all contributing objects
        for obj in context.object.ez_bake_object_props.overlay_layers[self.layer_index].objects:
            obj.object.select_set(True)
            context.view_layer.objects.active = obj.object

        bpy.ops.object.duplicate() # Duplicate to not alter original objects
        bpy.ops.object.convert(target='MESH') # Apply any modifiers
        bpy.ops.object.join()
        context.object.name = "EZBake_overlay_temp"

        bpy.ops.object.select_all(action='DESELECT')

        original_object.select_set(True)
        context.view_layer.objects.active = original_object
        return {'FINISHED'}



class OBJECT_OT_ez_bake_overlay_cleanup(bpy.types.Operator):
    bl_idname = "object.ez_bake_overlay_cleanup"
    bl_options = {"INTERNAL"}
    bl_label = "Cleanup after baking an overlay layer"

    def execute(self, context):
        original_object = context.object

        merged_object = context.scene.objects["EZBake_overlay_temp"]

        # Delete merged object
        bpy.ops.object.select_all(action='DESELECT')
        merged_object.select_set(True)
        context.view_layer.objects.active = merged_object
        bpy.ops.object.delete(use_global=False)

        # Select original object
        original_object.select_set(True)
        context.view_layer.objects.active = original_object
        return {'FINISHED'}


class EzBakeProgress(bpy.types.PropertyGroup):
    progress: bpy.props.IntProperty(default=0)
    total: bpy.props.IntProperty(default=0)

    def increment(self):
        self.progress += 1

    def get_progress_fac(self):
        if self.total == 0:
            return 0.0
        else:
            return self.progress / self.total

    def get_progress_string(self):
        return f'{self.progress} / {self.total}'

    def is_finished(self):
        return self.progress == self.total

    def reset(self):
        self.progress = 0
        self.total = 0


def check_material(material):
    if material is not None:
        bsdf_count = len([x for x in material.node_tree.nodes
                          if x.bl_idname == "ShaderNodeBsdfPrincipled"])
        return bsdf_count == 1


def prepare_material(material, map_name):
    if not check_material(material):
        return

    if map_name == "Color":
        disconnect_bsdf_property(material, 'Metallic', 0.0)
        disconnect_bsdf_property(material, 'Alpha', 1.0)
    elif map_name == "Metallic":
        disconnect_bsdf_property(material, 'Metallic', 0.0, view=True)
    elif map_name == "Alpha":
        disconnect_bsdf_property(material, 'Alpha', 0.0, view=True)


def restore_material(material, map_name):
    if not check_material(material):
        return

    if map_name == "Color":
        reconnect_bsdf_property(material, 'Metallic')
        reconnect_bsdf_property(material, 'Alpha')
    elif map_name == "Metallic":
        reconnect_bsdf_property(material, 'Metallic')
    elif map_name == "Alpha":
        reconnect_bsdf_property(material, 'Alpha')


# Get any materials needed to bake the object, including contributing objects
def get_materials(obj):
    materials = []

    for material_slot in obj.material_slots:
        mat = material_slot.material
        if mat is None:
            continue
        if mat not in materials:
            materials.append(mat)

    for layer in obj.ez_bake_object_props.overlay_layers:
        for obj in layer.objects:
            for material_slot in obj.object.material_slots:
                mat = material_slot.material
                if mat is None:
                    continue
                if mat not in materials:
                    materials.append(mat)

    return materials


def temp_node_name(property):
    return f'EZBake_{property}_temp'

# Disconnect the bsdf property (eg. Metallic) and set to a certain value while keeping original value aside
# If view is True, that property is connected to the viewer node
def disconnect_bsdf_property(material, property, new_value, view=False):
    node_tree = material.node_tree
    nodes = node_tree.nodes
    links = node_tree.links

    bsdf = next((n for n in nodes if n.bl_idname ==
                "ShaderNodeBsdfPrincipled"), None)
    if bsdf is None:
        raise Exception(f"No BSDF Found in material {material.name}")
    link = next((l for l in links if l.to_node ==
                bsdf and l.to_socket.identifier == property), None)

    if link is None:
        # Socket has no input, is just a value
        # Make new node to keep value
        temp_node = nodes.new("ShaderNodeValue")
        temp_node.location = bsdf.location - mathutils.Vector((170, 100))
        temp_node.name = temp_node_name(property)
        temp_node.outputs[0].default_value = bsdf.inputs[property].default_value
    else:
        # Socket is connected to something
        # Make a temporary reroute node
        temp_node = nodes.new("NodeReroute")
        temp_node.location = bsdf.location - mathutils.Vector((30, 100))
        temp_node.name = temp_node_name(property)
        links.new(link.from_socket, temp_node.inputs[0])
        links.remove(link)

    # Set new value
    bsdf.inputs[property].default_value = new_value

    if view:
        output_node = next((n for n in nodes if n.bl_idname ==
                           "ShaderNodeOutputMaterial"), None)
        if output_node is None:
            raise Exception(f"No Output node in material {material.name}")

        links.new(temp_node.outputs[0], output_node.inputs[0])


def reconnect_bsdf_property(material, property):
    node_tree = material.node_tree
    nodes = node_tree.nodes
    links = node_tree.links

    temp_node = next((n for n in nodes if n.name ==
                     temp_node_name(property)), None)
    if temp_node is None:
        raise Exception(f"Temp node not found in material {material.name}")

    bsdf = next((n for n in nodes if n.bl_idname ==
                "ShaderNodeBsdfPrincipled"), None)
    if bsdf is None:
        raise Exception(f"No BSDF Found in material {material.name}")

    if temp_node.bl_idname == 'ShaderNodeValue':
        # Copy value back
        bsdf.inputs[property].default_value = temp_node.outputs[0].default_value
    elif temp_node.bl_idname == 'NodeReroute':
        # Plug reroute node's input back in
        link = next(x for x in links if x.to_socket == temp_node.inputs[0])
        links.new(link.from_socket, bsdf.inputs[property])
        links.remove(link)

    nodes.remove(temp_node)

    # Reconnect BSDF to output incase the property was viewed
    output_node = next((n for n in nodes if n.bl_idname ==
                       "ShaderNodeOutputMaterial"), None)
    if output_node is None:
        raise Exception(f"No Output node in material {material.name}")

    links.new(bsdf.outputs[0], output_node.inputs[0])


def image_node_name(map_name):
    return f'EZBake_{map_name}_image'

# Add and select image node to bake to


def setup_image_node(material, map_name, image):
    nodes = material.node_tree.nodes
    node_name = image_node_name(map_name)
    node = nodes.get(node_name)

    if node is None:
        node = nodes.new("ShaderNodeTexImage")
        node.name = node_name
        node.image = image
        node.update()
    nodes.active = node


def cleanup_image_node(material, map_name):
    nodes = material.node_tree.nodes
    node_name = image_node_name(map_name)
    node = nodes.get(node_name)

    if node is not None:
        nodes.remove(node)


# Overlay decal over base object texture
def overlay_images(image_A, image_B, image_mask):
    width, height = image_A.size

    pixels_A = list(image_A.pixels[:])
    pixels_B = list(image_B.pixels[:])
    pixels_mask = list(image_mask.pixels[:])
    result_pixels = [0.0] * len(pixels_A)

    for y in range(height):
        for x in range(width):
            # Calculate the pixel index (4 values per pixel: R, G, B, A)
            idx = (y * width + x) * 4

            # Get pixel data from Image A and Image B
            r_A, g_A, b_A, alpha_A = pixels_A[idx:idx+4]
            r_B, g_B, b_B, alpha_B = pixels_B[idx:idx+4]
            r_mask, g_mask, b_mask, alpha_mask = pixels_mask[idx:idx+4]

            def lerp(a, b, t):
                return a + t * (b - a)

            is_alpha = image_B == image_mask
            if is_alpha:
                r_out = max(r_A, r_B)
                g_out = max(g_A, g_B)
                b_out = max(b_A, b_B)

                # r_out = r_A*r_B
                # g_out = g_A*g_B
                # b_out = b_A*b_B
            else:
                r_out = lerp(r_A, r_B, r_mask)
                g_out = lerp(g_A, g_B, r_mask)
                b_out = lerp(b_A, b_B, r_mask)

            result_pixels[idx:idx+4] = [r_out, g_out, b_out, max(alpha_A, r_mask)]
            # result_pixels[idx:idx+4] = [r_out, g_out, b_out, alpha_A * alpha_mask] # add option in the future

    image_A.pixels = result_pixels


# pack alpha (image_B) into image a (color)
def pack_alpha(image_A, image_B):
    width, height = image_A.size

    pixels_A = list(image_A.pixels[:])
    pixels_B = list(image_B.pixels[:])
    result_pixels = [0.0] * len(pixels_A)

    for y in range(height):
        for x in range(width):
            # Calculate the pixel index (4 values per pixel: R, G, B, A)
            idx = (y * width + x) * 4

            # Get pixel data from Image A and Image B
            r_A, g_A, b_A, alpha_A = pixels_A[idx:idx+4]
            r_B, g_B, b_B, alpha_B = pixels_B[idx:idx+4]

            result_pixels[idx:idx+4] = [r_A, g_A, b_A, r_B]

    image_A.pixels = result_pixels
    # result_image.save()


def combine_orm(ao_image, roughness_image, metallic_image, orm_name):
    # image_name = f'{obj.name}_{self.map_name}'
    resolution = 0
    if ao_image is not None:
        resolution = ao_image.size[0]
    elif roughness_image is not None:
        resolution = roughness_image.size[0]
    elif metallic_image is not None:
        resolution = metallic_image.size[0]

    if ao_image is None:
        ao_image = bpy.data.images.new(
            "EZBake_orm_ao_temp", width=resolution, height=resolution)
        ao_image.pixels = [1.0, 1.0, 1.0, 1.0] * (resolution * resolution)
    if roughness_image is None:
        roughness_image = bpy.data.images.new(
            "EZBake_orm_roughness_temp", width=resolution, height=resolution)
        roughness_image.pixels = [0.5, 0.5, 0.5,
                                  1.0] * (resolution * resolution)
    if metallic_image is None:
        metallic_image = bpy.data.images.new(
            "EZBake_orm_metallic_temp", width=resolution, height=resolution)
        metallic_image.pixels = [0.0, 0.0, 0.0,
                                 1.0] * (resolution * resolution)

    # if res changes
    orm_image = bpy.data.images.get(orm_name)
    if orm_image is not None and \
            (orm_image.size[0] != resolution
             or orm_image.size[1] != resolution):
        bpy.data.images.remove(orm_image)

    if orm_image is None:
        orm_image = bpy.data.images.new(
            orm_name, width=resolution, height=resolution)
        orm_image.colorspace_settings.name = 'Non-Color'

    ao_pixels = list(ao_image.pixels)
    roughness_pixels = list(roughness_image.pixels)
    metallic_pixels = list(metallic_image.pixels)

    orm_pixels = [0] * len(ao_pixels)

    for i in range(0, len(ao_pixels), 4):
        # R channel for AO, G channel for Roughness, B channel for Metallic
        orm_pixels[i] = ao_pixels[i]            # Red channel (AO)
        orm_pixels[i+1] = roughness_pixels[i+1]  # Green channel (Roughness)
        orm_pixels[i+2] = metallic_pixels[i+2]  # Blue channel (Metallic)
        # Alpha channel (optional, set to 1.0 for opaque)
        orm_pixels[i+3] = 1.0

    orm_image.pixels = orm_pixels

    image_name = orm_name

    return orm_image


def setup_materials(context):
    # Check if material already exists
    for obj in context.selected_objects:
        if bpy.data.materials.get(obj.name) is not None:
            return

        material = bpy.data.materials.new(name=obj.name)
        material.use_nodes = True

        nodes = material.node_tree.nodes
        links = material.node_tree.links

        nodes.clear()

        # Add a Principled BSDF shader node
        principled_bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
        principled_bsdf.location = (0, 0)

        # Add an output node
        material_output = nodes.new(type="ShaderNodeOutputMaterial")
        material_output.location = (400, 0)

        # Link Principled BSDF to Material Output
        links.new(principled_bsdf.outputs["BSDF"],
                  material_output.inputs["Surface"])

        # Function to add an image texture node and link it to a given principled input
        def add_image_texture(texture_image, principled_input, location):
            if texture_image:
                texture_node = nodes.new(type="ShaderNodeTexImage")
                texture_node.image = texture_image
                texture_node.location = location
                links.new(texture_node.outputs["Color"],
                          principled_bsdf.inputs[principled_input])

        # --- COLOR ---
        add_image_texture(bpy.data.images.get(
            f'{obj.name}_Color'), "Base Color", (-300, 200))
        # --- ALPHA ---
        add_image_texture(bpy.data.images.get(
            f'{obj.name}_Alpha'), "Alpha", (-300, -600))
        # --- EMISSION ---
        add_image_texture(bpy.data.images.get(
            f'{obj.name}_Emission'), "Emission Color", (-300, -800))
        if bpy.data.images.get(f'{obj.name}_Emission') is not None:
            principled_bsdf.inputs["Emission Strength"].default_value = 1.0


        # --- ORM ---
        if bpy.data.images.get(f'{obj.name}_ORM'):
            orm_node = nodes.new(type="ShaderNodeTexImage")
            orm_node.image = bpy.data.images.get(f'{obj.name}_ORM')
            orm_node.location = (-500, 0)

            # Create a Separate RGB node to split ORM channels
            separate_rgb = nodes.new(type="ShaderNodeSeparateRGB")
            separate_rgb.location = (-300, 0)
            links.new(orm_node.outputs["Color"], separate_rgb.inputs["Image"])

            # Link ORM channels to the Principled BSDF shader inputs
            # links.new(separate_rgb.outputs["R"], principled_bsdf.inputs["Ambient Occlusion"])
            links.new(separate_rgb.outputs["G"], principled_bsdf.inputs["Roughness"])
            links.new(separate_rgb.outputs["B"], principled_bsdf.inputs["Metallic"])

        else:
            # --- ROUGHNESS ---
            add_image_texture(bpy.data.images.get(
                f'{obj.name}_Roughness'), "Roughness", (-300, 0))
            # --- METALLIC ---
            add_image_texture(bpy.data.images.get(
                f'{obj.name}_Metallic'), "Metallic", (-300, -200))

        # --- NORMAL ---
        if bpy.data.images.get(f'{obj.name}_Normal'):
            normal_map_node = nodes.new(type="ShaderNodeNormalMap")
            normal_map_node.location = (-200, -400)

            normal_texture_node = nodes.new(type="ShaderNodeTexImage")
            normal_texture_node.image = bpy.data.images.get(
                f'{obj.name}_Normal')
            normal_texture_node.location = (-300, -400)

            links.new(normal_texture_node.outputs["Color"], normal_map_node.inputs["Color"])
            links.new(normal_map_node.outputs["Normal"], principled_bsdf.inputs["Normal"])



def register():
    bpy.utils.register_class(EzBakeProgress)
    bpy.utils.register_class(OBJECT_OT_ez_bake_overlay_setup)
    bpy.utils.register_class(OBJECT_OT_ez_bake_overlay_cleanup)
    bpy.types.Scene.ez_bake_progress = bpy.props.PointerProperty(
        type=EzBakeProgress)


def unregister():
    bpy.utils.unregister_class(EzBakeProgress)
    bpy.utils.unregister_class(OBJECT_OT_ez_bake_overlay_setup)
    bpy.utils.unregister_class(OBJECT_OT_ez_bake_overlay_cleanup)
    del bpy.types.Scene.ez_bake_progress
