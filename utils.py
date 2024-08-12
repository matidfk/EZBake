import bpy
import functools
import mathutils

class OBJECT_OT_ez_bake_contrib_setup(bpy.types.Operator):
    bl_idname = "object.ez_bake_contrib_setup"
    bl_options = {"INTERNAL"}
    bl_label = "Setup for baking contributing objects"
    def execute(self, context):
        context.scene.render.bake.use_selected_to_active = True
        context.scene.render.bake.use_clear = False

        # merge all contributing objects into one to lower the fixed overhead cost
        original_object = context.object
        bpy.ops.object.select_all(action='DESELECT')
        # select all contrib objects
        for obj in context.object.ez_bake_contributing_objects:
            obj.object.select_set(True)
            context.view_layer.objects.active = obj.object


        bpy.ops.object.duplicate()
        bpy.ops.object.join()
        
        context.object.name = "EZBake_temp"
        original_object.select_set(True)
        context.view_layer.objects.active = original_object
        return {'FINISHED'}

class OBJECT_OT_ez_bake_contrib_cleanup(bpy.types.Operator):
    bl_idname = "object.ez_bake_contrib_cleanup"
    bl_options = {"INTERNAL"}
    bl_label = "Cleanup for baking contributing objects"
    def execute(self, context):
        context.scene.render.bake.use_selected_to_active = True
        context.scene.render.bake.use_clear = False
        original_object = context.object
        merged_object = context.selected_objects[1]
        bpy.ops.object.select_all(action='DESELECT')

        merged_object.select_set(True)
        context.view_layer.objects.active = merged_object
        bpy.ops.object.delete(use_global=False)

        original_object.select_set(True)
        context.view_layer.objects.active = original_object
        return {'FINISHED'}


def add_bake(macro, context, name, type, non_color=False):
    setup_step = macro.define("OBJECT_OT_ez_bake_setup")
    setup_step.properties.name = name
    setup_step.properties.type = type
    setup_step.properties.non_color = non_color

    bake_step = macro.define("OBJECT_OT_bake")
    bake_step.properties.type = type
    bake_step.properties.save_mode = "INTERNAL"

    save_step = macro.define("OBJECT_OT_ez_bake_post")
    save_step.properties.name = name

    macro.steps += 1


class DEMOProperties(bpy.types.PropertyGroup):
    progress: bpy.props.IntProperty(default=0)
    total: bpy.props.IntProperty(default=0)


# Thank you Andrew Chinery https://blender.stackexchange.com/a/322063
def get_macro():
    # need to redefine the class to clear any previous steps assigned to the macro
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

class OBJECT_OT_ez_bake_setup(bpy.types.Operator):
    bl_idname = "object.ez_bake_setup"
    bl_options = {"INTERNAL"}
    bl_label = "Setup for baking"
    name: bpy.props.StringProperty()
    type: bpy.props.StringProperty() 
    non_color: bpy.props.BoolProperty()

    def execute(self, context):
        if self.name == "Color":
            setup_color(context)
        if self.name == "Metallic":
            setup_metallic(context)
        if self.name == "Alpha":
            setup_alpha(context)

        image_name = f'{context.object.name}_{self.name}'

        # Get texture image, create if non existent
        image = bpy.data.images.get(image_name)
        if image is None:
            bpy.ops.image.new(name=image_name, width=context.object.ez_bake_resolution,
                              height=context.object.ez_bake_resolution, alpha=False)
            image = bpy.data.images[image_name]

        if self.non_color:
            image.colorspace_settings.name = 'Non-Color'

        # Add image node to each material and select it
        for material_slot in context.object.material_slots:
            mat = material_slot.material
            node_name = f'EZBake_{self.name}'
            node = mat.node_tree.nodes.get(node_name)

            if node is None:
                node = mat.node_tree.nodes.new("ShaderNodeTexImage")
                node.name = node_name
                node.image = image
                node.update()
            mat.node_tree.nodes.active = node

        return {"FINISHED"}

class OBJECT_OT_ez_bake_post(bpy.types.Operator):
    bl_idname = "object.ez_bake_post"
    bl_options = {"INTERNAL"}
    bl_label = "Cleanup after baking"

    name: bpy.props.StringProperty()

    def execute(self, context):
        if self.name == "Color":
            unsetup_color(context)
        if self.name == "Metallic":
            unsetup_metallic(context)
        if self.name == "Alpha":
            unsetup_alpha(context)
        if context.object.ez_bake_save_to_file:
            image_name = f'{context.object.name}_{self.name}'
            image = bpy.data.images.get(image_name)
            table = {
                'JPG': ['jpg', 'JPEG'],
                'PNG': ['png', 'PNG'],
            }

            prefs_directory = context.preferences.addons[__package__].preferences.texture_directory
            image.filepath_raw = f'//{prefs_directory}/{image_name}.{table[context.object.ez_bake_file_format][0]}'
            image.file_format = table[context.object.ez_bake_file_format][1]
            image.save()

        # clean up nodes
        for material_slot in context.object.material_slots:
            mat = material_slot.material

            node_name = f'EZBake_{self.name}'
            node = mat.node_tree.nodes.get(node_name)
            if node is not None:
                mat.node_tree.nodes.remove(node)


        context.scene.demo.progress += 1
        print(f"FINISHED BAKING {self.name}")

        return {"FINISHED"}


def setup_color(context):
    for material_slot in context.object.material_slots:
        mat = material_slot.material
        output = next(x for x in mat.node_tree.nodes if x.bl_idname ==
                      "ShaderNodeOutputMaterial")
        bsdf = next(x for x in mat.node_tree.nodes if x.bl_idname ==
                    "ShaderNodeBsdfPrincipled")
        metallic_link = [x for x in mat.node_tree.links if x.to_node ==
                         bsdf and x.to_socket.identifier == 'Metallic']
        if len(metallic_link) == 0:
            # copy bare metallic value to new node
            node = mat.node_tree.nodes.new("ShaderNodeValue")
            node.location = bsdf.location - mathutils.Vector((170, 45))
            node.name = "EZBake_MetallicTemp"
            node.outputs[0].default_value = bsdf.inputs['Metallic'].default_value
            bsdf.inputs['Metallic'].default_value = 0.0
        else:
            # make temp reroute node
            metallic_link = metallic_link[0]
            node = mat.node_tree.nodes.new("NodeReroute")
            node.location = bsdf.location - mathutils.Vector((30, 80))
            node.name = "EZBake_MetallicTemp"
            mat.node_tree.links.new(metallic_link.from_socket, node.inputs[0])
            mat.node_tree.links.remove(metallic_link)
            bsdf.inputs['Metallic'].default_value = 0.0


def unsetup_color(context):
    for material_slot in context.object.material_slots:
        mat = material_slot.material
        output = next(x for x in mat.node_tree.nodes if x.bl_idname ==
                      "ShaderNodeOutputMaterial")
        bsdf = next(x for x in mat.node_tree.nodes if x.bl_idname ==
                    "ShaderNodeBsdfPrincipled")
        metallic_temp = next(
            x for x in mat.node_tree.nodes if x.name == 'EZBake_MetallicTemp')
        if metallic_temp.bl_idname == 'ShaderNodeValue':
            # copy value back to bsdf
            bsdf.inputs['Metallic'].default_value = metallic_temp.outputs[0].default_value
            mat.node_tree.nodes.remove(metallic_temp)
        elif metallic_temp.bl_idname == 'NodeReroute':
            # plug reroute back in
            metallic_link = next(
                x for x in mat.node_tree.links if x.to_socket == metallic_temp.inputs[0])
            mat.node_tree.links.new(
                metallic_link.from_socket, bsdf.inputs['Metallic'])
            mat.node_tree.links.remove(metallic_link)
            mat.node_tree.nodes.remove(metallic_temp)
        else:
            print("fuck")


def setup_metallic(context):
    for material_slot in context.object.material_slots:
        mat = material_slot.material
        output = next(x for x in mat.node_tree.nodes if x.bl_idname ==
                      "ShaderNodeOutputMaterial")
        bsdf = next(x for x in mat.node_tree.nodes if x.bl_idname ==
                    "ShaderNodeBsdfPrincipled")
        metallic_link = [x for x in mat.node_tree.links if x.to_node ==
                         bsdf and x.to_socket.identifier == 'Metallic']
        if len(metallic_link) == 0:
            # copy bare metallic value to new node
            node = mat.node_tree.nodes.new("ShaderNodeValue")
            node.location = bsdf.location - mathutils.Vector((170, 45))
            node.name = "EZBake_MetallicTemp"
            node.outputs[0].default_value = bsdf.inputs['Metallic'].default_value
            mat.node_tree.links.new(node.outputs[0], output.inputs[0])
        else:
            # make temp reroute node
            metallic_link = metallic_link[0]
            mat.node_tree.links.new(
                metallic_link.from_socket, output.inputs[0])


def unsetup_metallic(context):
    for material_slot in context.object.material_slots:
        mat = material_slot.material
        output = next(x for x in mat.node_tree.nodes if x.bl_idname ==
                      "ShaderNodeOutputMaterial")
        bsdf = next(x for x in mat.node_tree.nodes if x.bl_idname ==
                    "ShaderNodeBsdfPrincipled")
        metallic_temp = [
            x for x in mat.node_tree.nodes if x.name == 'EZBake_MetallicTemp']
        if len(metallic_temp) == 1:
            metallic_temp = metallic_temp[0]
            # copy value back to bsdf
            mat.node_tree.nodes.remove(metallic_temp)
            mat.node_tree.links.new(bsdf.outputs[0], output.inputs[0])
        else:
            # plug reroute back in
            metallic_link = next(
                x for x in mat.node_tree.links if x.to_socket == output.inputs[0])
            mat.node_tree.links.remove(metallic_link)
            mat.node_tree.links.new(bsdf.outputs[0], output.inputs[0])


def setup_alpha(context):
    for material_slot in context.object.material_slots:
        mat = material_slot.material
        output = next(x for x in mat.node_tree.nodes if x.bl_idname ==
                      "ShaderNodeOutputMaterial")
        bsdf = next(x for x in mat.node_tree.nodes if x.bl_idname ==
                    "ShaderNodeBsdfPrincipled")
        alpha_link = [x for x in mat.node_tree.links if x.to_node ==
                      bsdf and x.to_socket.identifier == 'Alpha']
        if len(alpha_link) == 0:
            # copy bare alpha value to new node
            node = mat.node_tree.nodes.new("ShaderNodeValue")
            node.location = bsdf.location - mathutils.Vector((170, 45))
            node.name = "EZBake_AlphaTemp"
            node.outputs[0].default_value = bsdf.inputs['Alpha'].default_value
            mat.node_tree.links.new(node.outputs[0], output.inputs[0])
        else:
            # make temp reroute node
            alpha_link = alpha_link[0]
            mat.node_tree.links.new(alpha_link.from_socket, output.inputs[0])


def unsetup_alpha(context):
    for material_slot in context.object.material_slots:
        mat = material_slot.material
        output = next(x for x in mat.node_tree.nodes if x.bl_idname ==
                      "ShaderNodeOutputMaterial")
        bsdf = next(x for x in mat.node_tree.nodes if x.bl_idname ==
                    "ShaderNodeBsdfPrincipled")
        alpha_temp = [
            x for x in mat.node_tree.nodes if x.name == 'EZBake_AlphaTemp']
        if len(alpha_temp) == 1:
            alpha_temp = alpha_temp[0]
            # copy value back to bsdf
            mat.node_tree.nodes.remove(alpha_temp)
            mat.node_tree.links.new(bsdf.outputs[0], output.inputs[0])
        else:
            # plug reroute back in
            alpha_link = next(
                x for x in mat.node_tree.links if x.to_socket == output.inputs[0])
            mat.node_tree.links.remove(alpha_link)
            mat.node_tree.links.new(bsdf.outputs[0], output.inputs[0])



def register():
    bpy.utils.register_class(OBJECT_OT_ez_bake_setup)
    bpy.utils.register_class(DEMOProperties)
    bpy.utils.register_class(OBJECT_OT_ez_bake_post)
    bpy.utils.register_class(OBJECT_OT_ez_bake_contrib_setup)
    bpy.utils.register_class(OBJECT_OT_ez_bake_contrib_cleanup)
    bpy.types.Scene.demo = bpy.props.PointerProperty(type=DEMOProperties)

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_ez_bake_setup)
    bpy.utils.unregister_class(DEMOProperties)
    bpy.utils.unregister_class(OBJECT_OT_ez_bake_post)
    bpy.utils.unregister_class(OBJECT_OT_ez_bake_contrib_setup)
    bpy.utils.unregister_class(OBJECT_OT_ez_bake_contrib_cleanup)
    del bpy.types.Scene.demo
