import bpy
import mathutils

from . import panel
from . import props

bl_info = {
    "name": "EZ Bake",
    "description": "Automate and streamline the baking process",
    "version": (0, 2),
    "blender": (5, 2, 0),
    "location": "View3D > Sidebar > EZ Bake",
    "category": "Object"
}



# BAKING PIPELINE:
#
# bake_pre
#    FOR EACH MAP {
#       bake_setup > bake > bake_cleanup
#       bake_setup > bake > bake_cleanup
#    }
# bake_post


# everything is added to one ez_bake_macro which then runs synchronously but without blocking the ui

class OBJECT_OT_ez_bake(bpy.types.Operator):
    bl_idname = "object.ez_bake"
    bl_label = "Bake"
    bl_options = {"REGISTER", "UNDO"}
    
    def execute(self, context):
        obj = context.object
        if obj is None:
            return
        
        obj_props = obj.ez_bake_object_props
        
        macro = get_macro()

        macro.define("object.ez_bake_pre")
        
        if obj_props.bake_color:
            add_bake(macro, "color")
        if obj_props.bake_roughness:
            add_bake(macro, "roughness")
        if obj_props.bake_metallic:
            add_bake(macro, "metallic")
        if obj_props.bake_normal:
            add_bake(macro, "normal")
        if obj_props.bake_emission:
            add_bake(macro, "emission")
        if obj_props.bake_alpha:
            add_bake(macro, "alpha")
        
        if obj_props.use_overlays:
            for layer_index, layer in enumerate(obj_props.overlay_layers):
                # always bake alpha, used as a mask
                add_bake(macro, "alpha", overlay_index=layer_index)
                
                if obj_props.bake_color:
                    add_bake(macro, "color", overlay_index=layer_index)
                if obj_props.bake_roughness:
                    add_bake(macro, "roughness", overlay_index=layer_index)
                if obj_props.bake_metallic:
                    add_bake(macro, "metallic", overlay_index=layer_index)
                if obj_props.bake_normal:
                    add_bake(macro, "normal", overlay_index=layer_index)
                if obj_props.bake_emission:
                    add_bake(macro, "emission", overlay_index=layer_index)
            
        
        macro.define("object.ez_bake_post")
        bpy.ops.object.ez_bake_macro("INVOKE_DEFAULT")
        return {'FINISHED'}

NON_COLOR_MAPS = ["normal", "roughness", "metallic", "alpha"]
def setup_target_image(object, map, overlay_index):
    TARGET_IMAGE_NAME = f'{object.name}_{map}'
    if overlay_index != -1:
        TARGET_IMAGE_NAME += f"_overlay{overlay_index}"
    target_image = bpy.data.images.get(TARGET_IMAGE_NAME)
    
    if overlay_index == -1:
        alpha=False
        color=(0,0,0,1)
    else:
        alpha=True
        color=(0,0,0,0)
            
    if target_image is None:
        bpy.ops.image.new(name=TARGET_IMAGE_NAME, width=2048, height=2048, alpha=alpha, color=color)
        target_image = bpy.data.images.get(TARGET_IMAGE_NAME)
    
    if map in NON_COLOR_MAPS:
        target_image.colorspace_settings.name = "Non-Color"
    
    return target_image


def setup_target_node_frame(material):
    nodes = material.node_tree.nodes
    
    frame = nodes.get("EZ_Bake_frame")
    
    if frame is None:
        frame = nodes.new("NodeFrame")
        frame.name = "EZ_Bake_frame"
        frame.label = "EZ Bake maps"
        frame.use_custom_color = True
        frame.color = (0.2, 0.2, 0.2)
    return frame

def setup_target_node(material, map, overlay_index):
    TARGET_NODE_NAME = f'EZ_Bake_{map}'
    if overlay_index != -1:
        TARGET_NODE_NAME = f"EZ_Bake_temp_{map}_overlay{overlay_index}"
    nodes = material.node_tree.nodes
    frame = setup_target_node_frame(material)
    
    target_node = nodes.get(TARGET_NODE_NAME)
    
    if target_node is None:
        target_node = nodes.new("ShaderNodeTexImage")
        target_node.name = TARGET_NODE_NAME
        target_node.label = TARGET_NODE_NAME
        if overlay_index == -1:
            target_node.parent = frame
            # find next free space
            for i in range(10):
                location = mathutils.Vector((300 + (i * 300), -200))
                if not any(n.location_absolute == location for n in nodes):
                    target_node.location_absolute = location
                    break
        else:
            target_node.location_absolute = (300, -600)
    
    target_node.select = True
    nodes.active = target_node
    
    return target_node
MAP_INPUT_DICT = {"color": "Base Color", "alpha": "Alpha", "roughness": "Roughness", "metallic": "Metallic", "emission": "Emission Color"}
def preview_shader_node_input(material, map):
    if map == "normal":
        return
    
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    shader_node = next((n for n in nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None)
    output_node = next((n for n in nodes if n.bl_idname == "ShaderNodeOutputMaterial"), None)
    input = shader_node.inputs.get(MAP_INPUT_DICT[map])
    
    if input.is_linked:
        links.new(input.links[0].from_socket, output_node.inputs[0])
    else:
        # create a temp node to connect to preview
        value = input.default_value
        NODE_TYPE_DICT = {"RGBA": "ShaderNodeRGB", "VALUE": "ShaderNodeValue"}
        temp_node = nodes.new(NODE_TYPE_DICT[input.type])
        temp_node.name = "EZ_Bake_temp"
        temp_node.outputs[0].default_value = value
        
        links.new(temp_node.outputs[0], output_node.inputs[0])

def reconnect_shader_node_to_output(material):
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    shader_node = next((n for n in nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None)
    output_node = next((n for n in nodes if n.bl_idname == "ShaderNodeOutputMaterial"), None)
    links.remove(output_node.inputs[0].links[0])
    links.new(shader_node.outputs[0], output_node.inputs[0])

def cleanup_temp_nodes(material):
    nodes = material.node_tree.nodes
    
    for n in nodes:
        if n.name.startswith("EZ_Bake_temp"):
            nodes.remove(n)

def setup_overlay(object, overlay_index):
    overlay_layer = object.ez_bake_object_props.overlay_layers[overlay_index]
    
    match overlay_layer.type:
        case "Object":
            bpy.ops.object.select_all(action="DESELECT")
            overlay_layer.object.select_set(True)
            object.select_set(True)
            bpy.context.view_layer.objects.active = object
        case "Collection":
            bpy.ops.object.select_all(action="DESELECT")
            for obj in overlay_layer.collection.objects:
                obj.select_set(True)
            object.select_set(True)
            bpy.context.view_layer.objects.active = object

def overlay_image(base_image, overlay_image, mask_image, map):
    node_group = bpy.data.node_groups.new("EZ_Bake_overlay_comp", "CompositorNodeTree")
    bpy.context.scene.compositing_node_group = node_group

    nodes = node_group.nodes
    links = node_group.links

    node_group.interface.new_socket(
        name="Image",
        in_out='OUTPUT',
        socket_type='NodeSocketColor',
    )

    base_image_node = nodes.new("CompositorNodeImage")
    base_image_node.location = (-200, 150)
    base_image_node.image = base_image

    overlay_image_node = nodes.new("CompositorNodeImage")
    overlay_image_node.location = (-200, 0)
    overlay_image_node.image = overlay_image

    mask_image_node = nodes.new("CompositorNodeImage")
    mask_image_node.location = (-200, -150)
    mask_image_node.image = mask_image
    
    alpha_over = nodes.new("CompositorNodeAlphaOver")
    links.new(base_image_node.outputs[0], alpha_over.inputs.get("Background"))
    links.new(overlay_image_node.outputs[0], alpha_over.inputs.get("Foreground"))
    links.new(mask_image_node.outputs[0], alpha_over.inputs.get("Factor"))
    
    last_node = alpha_over
    
    if map not in NON_COLOR_MAPS:
        convert = nodes.new("CompositorNodeConvertColorSpace")
        convert.to_color_space = "sRGB"
        links.new(alpha_over.outputs[0], convert.inputs.get("Image"))
        last_node = convert
    
    viewer = nodes.new("CompositorNodeViewer")
    viewer.location = (600, 0)
    links.new(last_node.outputs[0], viewer.inputs[0])

    output = nodes.new("NodeGroupOutput")
    output.location = (600, 100)
    links.new(last_node.outputs[0], output.inputs[0])
    
    bpy.ops.render.render(animation=False, write_still=False, use_viewport=False, layer="", scene="")
    
    viewer = bpy.data.images.get("Viewer Node")
    base_image.pixels = viewer.pixels
    
    bpy.data.node_groups.remove(node_group)
   
class OBJECT_OT_ez_bake_setup(bpy.types.Operator):
    bl_idname = "object.ez_bake_setup"
    bl_label = "bake setup"
    bl_options = {"INTERNAL"}
    
    map: bpy.props.StringProperty()
    overlay_index: bpy.props.IntProperty()
    
    def execute(self, context):
        obj = context.object
        
        # setup target image and nodes
        for mat in obj.data.materials:
            if map != "normal":
                preview_shader_node_input(mat, self.map)
            
            target_image = setup_target_image(obj, self.map, self.overlay_index)
            
            target_node = setup_target_node(mat, self.map, self.overlay_index)
            target_node.image = target_image
        # setup correct preview in overlay object
        if self.overlay_index != -1:
            layer = obj.ez_bake_object_props.overlay_layers[self.overlay_index]
            match layer.type:
                case "Object":
                    for mat in layer.object.data.materials:
                        preview_shader_node_input(mat, self.map)
                case "Collection":
                    for o in layer.collection.objects:
                        for mat in o.data.materials:
                            preview_shader_node_input(mat, self.map)
                    
                    
        
        # setup overlay and related bake settings
        context.scene.render.bake.use_clear = True
        if self.overlay_index != -1:
            context.scene.render.bake.use_selected_to_active = True
            context.scene.render.bake.margin = 0
            setup_overlay(obj, self.overlay_index)
        else:
            context.scene.render.bake.use_selected_to_active = False
            context.scene.render.bake.margin = 16
        
            
        return {'FINISHED'}

def add_bake(macro, map, overlay_index=-1):
    setup = macro.define("object.ez_bake_setup")
    setup.properties.map = map
    setup.properties.overlay_index = overlay_index
    
    bake = macro.define("object.bake")
    bake.properties.type = "EMIT"
    if map == "normal":
        bake.properties.type = "NORMAL"
    
    cleanup = macro.define("object.ez_bake_cleanup")
    cleanup.properties.map = map
    cleanup.properties.overlay_index = overlay_index
    
    
    message = f"Baking {map}"
    if overlay_index != -1:
        message += " overlay"
    message += "..."
    message += ";"
    
    bpy.context.scene.ez_bake_steps += message

def get_macro():
    class OBJECT_OT_ez_bake_macro(bpy.types.Macro):
        bl_idname = "object.ez_bake_macro"
        bl_label = "EZ Bake Macro"
        bl_options = {"UNDO"}
        
        @classmethod
        def poll(cls, context):
            return context.active_object is not None
    
    if hasattr(bpy.types, "OBJECT_OT_ez_bake_macro"):
        bpy.utils.unregister_class(bpy.types.OBJECT_OT_ez_bake_macro)
    
    bpy.utils.register_class(OBJECT_OT_ez_bake_macro)
    macro = OBJECT_OT_ez_bake_macro
    
    return macro

class OBJECT_OT_ez_bake_cleanup(bpy.types.Operator):
    bl_idname = "object.ez_bake_cleanup"
    bl_label = "bake cleanup"
    bl_options = {"INTERNAL"}
    
    overlay_index: bpy.props.IntProperty()
    map: bpy.props.StringProperty()
    
    def execute(self, context):
        obj = context.object
        obj_props = obj.ez_bake_object_props
        
        for mat in obj.data.materials:
            reconnect_shader_node_to_output(mat)
            cleanup_temp_nodes(mat)
        if self.overlay_index != -1:
            layer = obj.ez_bake_object_props.overlay_layers[self.overlay_index]
            match layer.type:
                case "Object":
                    for mat in layer.object.data.materials:
                        reconnect_shader_node_to_output(mat)
                        cleanup_temp_nodes(mat)
                case "Collection":
                    for o in layer.collection.objects:
                        for mat in o.data.materials:
                            reconnect_shader_node_to_output(mat)
                            cleanup_temp_nodes(mat)
                        
            
            if self.map != "alpha":
                overlay_image(bpy.data.images.get(f"{obj.name}_{self.map}"), bpy.data.images.get(f"{obj.name}_{self.map}_overlay{self.overlay_index}"), bpy.data.images.get(f"{obj.name}_alpha_overlay{self.overlay_index}"), self.map)
        
        if not (self.overlay_index != -1 and self.map == "alpha"):
            image = bpy.data.images.get(f"{obj.name}_{self.map}")
            image.pack()
            
            FORMAT_DICT = {
            #  option fileext blenderformat
                "JPG": ["jpg", "JPEG"],
                "PNG": ["png", "PNG"]
            }
            if obj_props.save_path != "":
                file_ext = FORMAT_DICT[obj_props.file_format][0]
                image.file_format = FORMAT_DICT[obj_props.file_format][1]
                image.filepath_raw = f"{obj_props.save_path}/{obj.name}_{self.map}.{file_ext}"
                image.save()
            
        
        context.scene.ez_bake_current_step += 1
        return {'FINISHED'}

class OBJECT_OT_ez_bake_pre(bpy.types.Operator):
    bl_idname = "object.ez_bake_pre"
    bl_label = "first bake setup - before running any bakes"
    bl_options = {"INTERNAL"}
    
    def execute(self, context):
        context.scene.render.engine = "CYCLES"
        context.scene.cycles.samples = context.object.ez_bake_object_props.samples
        
        return {'FINISHED'}

def setup_update_baked_material(obj):
    material = bpy.data.materials.get(obj.name)
    
    if material is None:
        material = bpy.data.materials.new(name=obj.name)
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
        def add_image_texture(map, location):
            image_name = f"{obj.name}_{map}"
            image = bpy.data.images.get(image_name)
            if image:
                texture_node = nodes.new(type="ShaderNodeTexImage")
                texture_node.image = image
                texture_node.location = location
                principled_input = MAP_INPUT_DICT[map]
                links.new(texture_node.outputs["Color"],
                          principled_bsdf.inputs[principled_input])

        # --- COLOR ---
        add_image_texture("color", (-300, 200))
        # --- ALPHA ---
        # only add alpha if selected, otherwise it is a generated all white image needed only for overlays
        if obj.ez_bake_object_props.bake_alpha:
            add_image_texture("alpha", (-300, -600))
        # --- EMISSION ---
        add_image_texture("emission", (-300, -800))
        if bpy.data.images.get(f'{obj.name}_Emission') is not None:
            principled_bsdf.inputs["Emission Strength"].default_value = 1.0


        # --- ORM ---
#        if bpy.data.images.get(f'{obj.name}_ORM'):
#            orm_node = nodes.new(type="ShaderNodeTexImage")
#            orm_node.image = bpy.data.images.get(f'{obj.name}_ORM')
#            orm_node.location = (-500, 0)

#            # Create a Separate RGB node to split ORM channels
#            separate_rgb = nodes.new(type="ShaderNodeSeparateRGB")
#            separate_rgb.location = (-300, 0)
#            links.new(orm_node.outputs["Color"], separate_rgb.inputs["Image"])

#            # Link ORM channels to the Principled BSDF shader inputs
#            # links.new(separate_rgb.outputs["R"], principled_bsdf.inputs["Ambient Occlusion"])
#            links.new(separate_rgb.outputs["G"], principled_bsdf.inputs["Roughness"])
#            links.new(separate_rgb.outputs["B"], principled_bsdf.inputs["Metallic"])

#        else:
        # --- ROUGHNESS ---
        add_image_texture("roughness", (-300, 0))
        # --- METALLIC ---
        add_image_texture("metallic", (-300, -200))

        # --- NORMAL ---
        if bpy.data.images.get(f'{obj.name}_normal'):
            normal_map_node = nodes.new(type="ShaderNodeNormalMap")
            normal_map_node.location = (-200, -400)

            normal_texture_node = nodes.new(type="ShaderNodeTexImage")
            normal_texture_node.image = bpy.data.images.get(
                f'{obj.name}_normal')
            normal_texture_node.location = (-300, -400)

            links.new(normal_texture_node.outputs["Color"], normal_map_node.inputs["Color"])
            links.new(normal_map_node.outputs["Normal"], principled_bsdf.inputs["Normal"])


class OBJECT_OT_ez_bake_post(bpy.types.Operator):
    bl_idname = "object.ez_bake_post"
    bl_label = "final bake cleanup - after running all bakes"
    bl_options = {"INTERNAL"}
    
    def execute(self, context):
        obj = context.object
        
        context.scene.ez_bake_current_step = 0
        context.scene.ez_bake_steps = ""
        
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        
        if obj.ez_bake_object_props.setup_update_baked_material:
            setup_update_baked_material(obj)
        
        return {'FINISHED'}

def get_current_step():
    return bpy.context.scene.ez_bake_steps.split(";")[bpy.context.scene.ez_bake_current_step]

def get_progress_factor():
    steps = len(bpy.context.scene.ez_bake_steps.split(";")) - 1.0
    return bpy.context.scene.ez_bake_current_step / steps

def register():
    panel.register()
    props.register()
    
    bpy.utils.register_class(OBJECT_OT_ez_bake)
    
    bpy.utils.register_class(OBJECT_OT_ez_bake_pre)
    bpy.utils.register_class(OBJECT_OT_ez_bake_post)
    
    bpy.utils.register_class(OBJECT_OT_ez_bake_setup)
    bpy.utils.register_class(OBJECT_OT_ez_bake_cleanup)
    
    bpy.utils.register_class(EzBakeOverlayLayer)
    
    bpy.types.Scene.ez_bake_steps = bpy.props.StringProperty()
    bpy.context.scene.ez_bake_steps = ""
    bpy.types.Scene.ez_bake_current_step = bpy.props.IntProperty()
    bpy.context.scene.ez_bake_current_step = 0


def unregister():
    panel.unregister()
    props.unregister()
    
    bpy.utils.unregister_class(OBJECT_OT_ez_bake)
    
    bpy.utils.unregister_class(OBJECT_OT_ez_bake_pre)
    bpy.utils.unregister_class(OBJECT_OT_ez_bake_post)
    
    bpy.utils.unregister_class(OBJECT_OT_ez_bake_setup)
    bpy.utils.unregister_class(OBJECT_OT_ez_bake_cleanup)
    

if __name__ == "__main__":
    register()
