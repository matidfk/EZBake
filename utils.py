import bpy
import mathutils


class OBJECT_OT_ez_bake_contrib_setup(bpy.types.Operator):
    bl_idname = "object.ez_bake_contrib_setup"
    bl_options = {"INTERNAL"}
    bl_label = "Setup for baking contributing objects"

    """Merge contributing objects into one as there is
    a high fixed cost for each object"""

    def execute(self, context):

        original_object = context.object
        bpy.ops.object.select_all(action='DESELECT')

        # Join copies of all contributing objects
        for obj in context.object.ez_bake_contributing_objects:
            obj.object.select_set(True)
            context.view_layer.objects.active = obj.object
        bpy.ops.object.duplicate()
        bpy.ops.object.join()
        context.object.name = "EZBake_contributing_temp"

        bpy.ops.object.select_all(action='DESELECT')

        original_object.select_set(True)
        context.view_layer.objects.active = original_object
        return {'FINISHED'}


class OBJECT_OT_ez_bake_contrib_cleanup(bpy.types.Operator):
    bl_idname = "object.ez_bake_contrib_cleanup"
    bl_options = {"INTERNAL"}
    bl_label = "Cleanup for baking contributing objects"

    def execute(self, context):
        original_object = context.object

        merged_object = context.scene.objects["EZBake_contributing_temp"]

        # Delete merged object
        bpy.ops.object.select_all(action='DESELECT')
        merged_object.select_set(True)
        context.view_layer.objects.active = merged_object
        bpy.ops.object.delete(use_global=False)

        # Select original object
        original_object.select_set(True)
        context.view_layer.objects.active = original_object
        return {'FINISHED'}


def add_bake(macro, context, map_name, map_type, non_color=False):
    setup_step = macro.define("OBJECT_OT_ez_bake_setup")
    setup_step.properties.map_name = map_name
    setup_step.properties.map_type = map_type
    setup_step.properties.non_color = non_color

    bake_step = macro.define("OBJECT_OT_bake")
    bake_step.properties.type = map_type
    bake_step.properties.save_mode = "INTERNAL"

    save_step = macro.define("OBJECT_OT_ez_bake_post")
    save_step.properties.map_name = map_name

    macro.steps += 1

    if context.object.ez_bake_use_contributing_objects:
        setup_step = macro.define("OBJECT_OT_ez_bake_setup")
        setup_step.properties.map_name = map_name
        setup_step.properties.map_type = map_type
        setup_step.properties.non_color = non_color
        setup_step.properties.contrib_pass = True

        bake_step = macro.define("OBJECT_OT_bake")
        bake_step.properties.type = map_type
        bake_step.properties.save_mode = "INTERNAL"

        save_step = macro.define("OBJECT_OT_ez_bake_post")
        save_step.properties.map_name = map_name
        save_step.properties.contrib_pass = True

        macro.steps += 1


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


# Thank you Andrew Chinery https://blender.stackexchange.com/a/322063
def get_macro():
    # redefine the class to clear any previous steps assigned to the macro
    class OBJECT_OT_ez_bake_macro(bpy.types.Macro):
        bl_idname = "object.ez_bake_macro"
        bl_label = "Bake Macro"
        bl_options = {"INTERNAL", "MACRO"}

        steps = 0

    # unregister any previous macro
    if hasattr(bpy.types, "OBJECT_OT_ez_bake_macro"):
        bpy.utils.unregister_class(bpy.types.OBJECT_OT_ez_bake_macro)

    bpy.utils.register_class(OBJECT_OT_ez_bake_macro)
    return OBJECT_OT_ez_bake_macro

def prepare_material(material, map_name):
    if map_name == "Color":
        disconnect_bsdf_property(material, 'Metallic', 0.0)
        disconnect_bsdf_property(material, 'Alpha', 1.0)
    elif map_name == "Metallic":
        disconnect_bsdf_property(material, 'Metallic', 0.0, view=True)
    elif map_name == "Alpha":
        disconnect_bsdf_property(material, 'Alpha', 0.0, view=True)

def restore_material(material, map_name):
    if map_name == "Color":
        reconnect_bsdf_property(material, 'Metallic')
        reconnect_bsdf_property(material, 'Alpha')
    elif map_name == "Metallic":
        reconnect_bsdf_property(material, 'Metallic')
    elif map_name == "Alpha":
        reconnect_bsdf_property(material, 'Alpha')

def get_materials(obj):
    materials = []

    for material_slot in obj.material_slots:
        mat = material_slot.material
        if mat is None:
            continue
        if mat not in materials:
            materials.append(mat)

    for obj in obj.ez_bake_contributing_objects:
        for material_slot in obj.object.material_slots:
            mat = material_slot.material
            if mat is None:
                continue
            if mat not in materials:
                materials.append(mat)

    return materials
            

class OBJECT_OT_ez_bake_setup(bpy.types.Operator):
    bl_idname = "object.ez_bake_setup"
    bl_options = {"INTERNAL"}
    bl_label = "Setup for baking"
    map_name: bpy.props.StringProperty()
    map_type: bpy.props.StringProperty()
    non_color: bpy.props.BoolProperty()
    contrib_pass: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        obj = context.object
        # Disconnect any BSDF Properties that need to be disconnected 
        for material in get_materials(obj):
            prepare_material(material, self.map_name)


        if self.contrib_pass:
            context.scene.objects["EZBake_contributing_temp"].select_set(True)
            context.view_layer.objects.active = obj
            context.scene.render.bake.use_selected_to_active = True
            context.scene.render.bake.use_clear = False
            context.scene.render.bake.margin = 0
        else:
            context.scene.render.bake.use_selected_to_active = False
            context.scene.render.bake.use_clear = True

        
        image_name = f'{obj.name}_{self.map_name}'
        if self.contrib_pass:
            image_name += "_contrib"

        # Get texture image
        image = bpy.data.images.get(image_name)

        # If resolution has changed
        if image is not None and \
                (image.size[0] != int(obj.ez_bake_resolution)
                 or image.size[1] != int(obj.ez_bake_resolution)):
            bpy.data.images.remove(image)

        if image is None:
            if self.contrib_pass:
                # Contributing pass needs alpha
                bpy.ops.image.new(name=image_name, width=int(obj.ez_bake_resolution),
                                  height=int(obj.ez_bake_resolution), alpha=True, color=(0,0,0,0))
            else:
                bpy.ops.image.new(name=image_name, width=int(obj.ez_bake_resolution),
                                  height=int(obj.ez_bake_resolution), alpha=False)

            image = bpy.data.images[image_name]

        if self.non_color:
            image.colorspace_settings.name = 'Non-Color'

        # Setup image nodes
        for material in get_materials(obj):
            setup_image_node(material, self.map_name, image)

        return {"FINISHED"}


class OBJECT_OT_ez_bake_post(bpy.types.Operator):
    bl_idname = "object.ez_bake_post"
    bl_options = {"INTERNAL"}
    bl_label = "Cleanup after baking"

    map_name: bpy.props.StringProperty()
    contrib_pass: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        obj = context.object
        # Reconnect BSDF properties
        for material in get_materials(obj):
            restore_material(material, self.map_name)

        if self.contrib_pass:
            # base image should already exist
            base_image = bpy.data.images[f'{obj.name}_{self.map_name}']
            overlay_image = bpy.data.images[f'{obj.name}_{self.map_name}_contrib']
            overlay_images(base_image, overlay_image)
            bpy.data.images.remove(overlay_image)
            base_image.save()
            # Show base image in any open editor
            for area in context.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    area.spaces.active.image = base_image

            print(f"EZBAKE: Finished baking {base_image.name} Overlay")
        else:
            image_name = f'{obj.name}_{self.map_name}'
            image = bpy.data.images.get(image_name)
            table = {
                'JPG': ['jpg', 'JPEG'],
                'PNG': ['png', 'PNG'],
            }

            prefs = context.preferences.addons[__package__].preferences
            prefs_directory = prefs.texture_directory
            file_ext = table[obj.ez_bake_file_format][0]
            format = table[obj.ez_bake_file_format][1]

            image.filepath_raw = f'//{prefs_directory}/{image_name}.{file_ext}'
            image.file_format = format

            image.save()
            print(f"EZBAKE: Finished baking {image_name}.{file_ext}")

        # clean up nodes
        for material in get_materials(obj):
            cleanup_image_node(material, self.map_name)


        # only works because we always do metallic after roughness and AO
        if self.map_name == "Metallic" and context.scene.ez_bake_pack_orm:
            image_name = f'{obj.name}_ORM'
            image = combine_orm(bpy.data.images.get(f'{obj.name}_AO'), bpy.data.images.get(f'{obj.name}_Roughness'), bpy.data.images.get(f'{obj.name}_Metallic'), image_name)
            table = {
                'JPG': ['jpg', 'JPEG'],
                'PNG': ['png', 'PNG'],
            }

            prefs = context.preferences.addons[__package__].preferences
            prefs_directory = prefs.texture_directory
            file_ext = table[obj.ez_bake_file_format][0]
            format = table[obj.ez_bake_file_format][1]

            image.filepath_raw = f'//{prefs_directory}/{image_name}.{file_ext}'
            image.file_format = format

            image.save()
            print(f"EZBAKE: Finished combining {image_name}.{file_ext}")

        context.scene.ez_bake_progress.increment()

        return {"FINISHED"}


def temp_node_name(property):
    return f'EZBake_{property}_temp'

# Disconnect the bsdf property (eg. Metallic) and set to a certain value while keeping original value aside
# If view is True, that property is connected to the viewer node
def disconnect_bsdf_property(material, property, new_value, view=False):
    node_tree = material.node_tree
    nodes = node_tree.nodes
    links = node_tree.links

    bsdf = next((n for n in nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None)
    if bsdf is None:
        raise Exception(f"No BSDF Found in material {material.name}")
    link = next((l for l in links if l.to_node == bsdf and l.to_socket.identifier == property), None)

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
        output_node = next((n for n in nodes if n.bl_idname == "ShaderNodeOutputMaterial"), None)
        if output_node is None:
            raise Exception(f"No Output node in material {material.name}")

        links.new(temp_node.outputs[0], output_node.inputs[0])

def reconnect_bsdf_property(material, property):
    node_tree = material.node_tree
    nodes = node_tree.nodes
    links = node_tree.links

    temp_node = next((n for n in nodes if n.name == temp_node_name(property)), None)
    if temp_node is None:
        raise Exception(f"Temp node not found in material {material.name}")

    bsdf = next((n for n in nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None)
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
    output_node = next((n for n in nodes if n.bl_idname == "ShaderNodeOutputMaterial"), None)
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
def overlay_images(image_A, image_B):
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
            
            def lerp(a, b, t):
                return a + t * (b - a)
            
            r_out = lerp(r_A, r_B, alpha_B)
            g_out = lerp(g_A, g_B, alpha_B)
            b_out = lerp(b_A, b_B, alpha_B)

            result_pixels[idx:idx+4] = [r_out, g_out, b_out, 1.0]

    image_A.pixels = result_pixels
    # result_image.save()

def combine_orm(ao_image, roughness_image, metallic_image, orm_name):
    #image_name = f'{obj.name}_{self.map_name}'
    resolution = 0
    if ao_image is not None:
        resolution = ao_image.size[0]
    elif roughness_image is not None:
        resolution = roughness_image.size[0]
    elif metallic_image is not None:
        resolution = metallic_image.size[0]


    if ao_image is None:
        print("makign ao image")
        ao_image = bpy.data.images.new("EZBake_orm_ao_temp", width=resolution, height=resolution)
        ao_image.pixels = [1.0, 1.0, 1.0, 1.0] * (resolution * resolution)
    if roughness_image is None:
        roughness_image = bpy.data.images.new("EZBake_orm_roughness_temp", width=resolution, height=resolution)
        roughness_image.pixels = [0.5, 0.5, 0.5, 1.0] * (resolution * resolution)
    if metallic_image is None:
        metallic_image = bpy.data.images.new("EZBake_orm_metallic_temp", width=resolution, height=resolution)
        metallic_image.pixels = [0.0, 0.0, 0.0, 1.0] * (resolution * resolution)

    # if res changes
    orm_image = bpy.data.images.get(orm_name)
    if orm_image is not None and \
            (orm_image.size[0] != resolution
             or orm_image.size[1] != resolution):
        bpy.data.images.remove(orm_image)

    if orm_image is None:
        orm_image = bpy.data.images.new(orm_name, width=resolution, height=resolution)
        orm_image.colorspace_settings.name = 'Non-Color'

    ao_pixels = list(ao_image.pixels)
    roughness_pixels = list(roughness_image.pixels)
    metallic_pixels = list(metallic_image.pixels)

    orm_pixels = [0] * len(ao_pixels)

    for i in range(0, len(ao_pixels), 4):
        # R channel for AO, G channel for Roughness, B channel for Metallic
        orm_pixels[i] = ao_pixels[i]            # Red channel (AO)
        orm_pixels[i+1] = roughness_pixels[i+1] # Green channel (Roughness)
        orm_pixels[i+2] = metallic_pixels[i+2]  # Blue channel (Metallic)
        orm_pixels[i+3] = 1.0                   # Alpha channel (optional, set to 1.0 for opaque)

    orm_image.pixels = orm_pixels


    image_name = orm_name

    return orm_image

def register():
    bpy.utils.register_class(OBJECT_OT_ez_bake_setup)
    bpy.utils.register_class(EzBakeProgress)
    bpy.utils.register_class(OBJECT_OT_ez_bake_post)
    bpy.utils.register_class(OBJECT_OT_ez_bake_contrib_setup)
    bpy.utils.register_class(OBJECT_OT_ez_bake_contrib_cleanup)
    bpy.types.Scene.ez_bake_progress = bpy.props.PointerProperty(
        type=EzBakeProgress)


def unregister():
    bpy.utils.unregister_class(OBJECT_OT_ez_bake_setup)
    bpy.utils.unregister_class(EzBakeProgress)
    bpy.utils.unregister_class(OBJECT_OT_ez_bake_post)
    bpy.utils.unregister_class(OBJECT_OT_ez_bake_contrib_setup)
    bpy.utils.unregister_class(OBJECT_OT_ez_bake_contrib_cleanup)
    del bpy.types.Scene.ez_bake_progress
