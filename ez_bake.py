bl_info = {
    "name": "EZ Bake",
    "blender": (4, 1, 1),
    "location": "View3D > Sidebar > EZ Bake",
    "category": "Object",
}

import bpy
import mathutils

# add enum for jpg or png, add option for directory instead of fixed, try add auto setup of new mat

class EzBakePanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_ez_bake"
    bl_label = "EZ Bake"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EZ Bake"
    bl_context = "objectmode"
    # bl_options = {"DEFAULT_CLOSED"}


    def draw(self, context):
        layout = self.layout
        layout.prop(context.object, "ez_bake_resolution")
        layout.prop(context.object, "ez_bake_save_to_file")
        layout.prop(context.object, "ez_bake_samples")
        layout.operator("object.ez_bake")

        (header, panel) = layout.panel('Maps')
        header.label(text="Maps")
        panel = panel.grid_flow(columns = 2)
        panel.prop(context.object, "ez_bake_color")
        panel.prop(context.object, "ez_bake_roughness")
        panel.prop(context.object, "ez_bake_metallic")
        panel.prop(context.object, "ez_bake_emission")
        panel.prop(context.object, "ez_bake_normal")
        panel.prop(context.object, "ez_bake_alpha")


class EzBake(bpy.types.Operator):
    bl_label = "EZ Bake"
    bl_idname = "object.ez_bake"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.object.ez_bake_color:
            bake_boilerplate(context, "Color", "DIFFUSE", (-1000, 0))
        if context.object.ez_bake_roughness:
            bake_boilerplate(context, "Roughness", "ROUGHNESS", (-1000, -300))
        if context.object.ez_bake_metallic:
            # setup_metallic(context)
            bake_boilerplate(context, "Metallic", "EMIT", (-1000, -600))
        if context.object.ez_bake_emission:
            bake_boilerplate(context, "Emission", "EMIT", (-1000, -900))
        if context.object.ez_bake_normal:
            bake_boilerplate(context, "Normal", "NORMAL", (-1000, -1200))
        if context.object.ez_bake_alpha:
            bake_boilerplate(context, "Alpha", "EMIT", (-1000, -1500))



        return {'FINISHED'}

# def setup_metallic(context):
#     for material_slot in context.object.material_slots:
#         mat = material_slot.material
#         output = next(x for x in mat.node_tree.nodes if x.bl_idname == "ShaderNodeOutputMaterial")
#         bsdf = next(x for x in mat.node_tree.links if x.to_node == output).from_node
#         metallic_link = next(x for x in mat.node_tree.links if x.to_node == bsdf)
#         if metallic_link is not None:
#             metallic_link.to_node = output
#             metallic_link.to_socket = output.inputs[0]





def bake_boilerplate(context, name, type, node_location):
    image_name = f'{context.object.name}_{name}'
    resolution = context.object.ez_bake_resolution

    image = bpy.data.images.get(image_name)
    if image is None:
        bpy.ops.image.new(name=image_name, width=resolution, height=resolution, alpha=False)
        image = bpy.data.images[image_name]

    for material_slot in context.object.material_slots:
        mat = material_slot.material

        node_name = f'EZBake_{name}'
        node = mat.node_tree.nodes.get(node_name)
        if node is None:
            node = mat.node_tree.nodes.new("ShaderNodeTexImage")
            node.name = node_name
            node.image = image
            node.location = mathutils.Vector(node_location)
            node.update()

        # node.select = True
        mat.node_tree.nodes.active = node

    original_samples = context.scene.cycles.samples

    context.scene.render.bake.use_pass_direct = False
    context.scene.render.bake.use_pass_indirect = False
    context.scene.cycles.samples = context.object.ez_bake_samples
    context.scene.cycles.use_denoising = False


    bpy.ops.object.bake(type=type)

    if context.object.ez_bake_save_to_file:
        image.filepath_raw = f'//Textures/{image_name}.jpg'
        image.file_format = 'JPEG'
        image.save()
    # bpy.ops.object.bake('INVOKE_DEFAULT', type=type)
    context.scene.cycles.samples = original_samples

def register():
    bpy.utils.register_class(EzBakePanel)
    bpy.utils.register_class(EzBake)
    bpy.types.Object.ez_bake_resolution = bpy.props.IntProperty(name = "Resolution", default=1024)
    bpy.types.Object.ez_bake_save_to_file = bpy.props.BoolProperty(name = "Save to file", default = True)
    bpy.types.Object.ez_bake_samples = bpy.props.IntProperty(name = "Samples", default = 32)
    bpy.types.Object.ez_bake_color = bpy.props.BoolProperty(name = "Color", default = True)
    bpy.types.Object.ez_bake_roughness = bpy.props.BoolProperty(name = "Roughness", default = True)
    bpy.types.Object.ez_bake_metallic = bpy.props.BoolProperty(name = "Metallic", default = True)
    bpy.types.Object.ez_bake_emission = bpy.props.BoolProperty(name = "Emission", default = True)
    bpy.types.Object.ez_bake_normal = bpy.props.BoolProperty(name = "Normal", default = True)
    bpy.types.Object.ez_bake_alpha = bpy.props.BoolProperty(name = "Alpha", default = True)
def unregister():
    bpy.utils.unregister_class(EzBakePanel)
    bpy.utils.unregister_class(EzBake)