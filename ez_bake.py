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
        if context.active_object is None:
            return
        layout = self.layout
        layout.prop(context.object, "ez_bake_resolution")
        layout.prop(context.object, "ez_bake_save_to_file")
        format = layout.row()
        format.prop(context.object, "ez_bake_file_format", expand=True)
        format.active = context.object.ez_bake_save_to_file
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

        layout.prop(context.scene, "ez_bake_auto_refresh")


class EzBake(bpy.types.Operator):
    bl_label = "EZ Bake"
    bl_idname = "object.ez_bake"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        for material_slot in context.object.material_slots:
            mat = material_slot.material
            if len([x for x in mat.node_tree.nodes if x.bl_idname == "ShaderNodeBsdfPrincipled"]) != 1:
                self.report({"ERROR"},f'{len([x for x in mat.node_tree.nodes if x.bl_idname == "ShaderNodeBsdfPrincipled"])} BSDFs found in material {mat.name}')
                return {'CANCELLED'}

        render_engine = bpy.data.scenes["Scene"].render.engine
        bpy.data.scenes["Scene"].render.engine = 'CYCLES'
        if context.object.ez_bake_color:
            setup_color(context)
            bake_boilerplate(context, "Color", "DIFFUSE", (-1000, 0), False)
            unsetup_color(context)
        if context.object.ez_bake_roughness:
            bake_boilerplate(context, "Roughness", "ROUGHNESS", (-1000, -300), True)
        if context.object.ez_bake_metallic:
            setup_metallic(context)
            bake_boilerplate(context, "Metallic", "EMIT", (-1000, -600), True)
            unsetup_metallic(context)
        if context.object.ez_bake_emission:
            bake_boilerplate(context, "Emission", "EMIT", (-1000, -900), False)
        if context.object.ez_bake_normal:
            bake_boilerplate(context, "Normal", "NORMAL", (-1000, -1200), True)
        if context.object.ez_bake_alpha:
            setup_alpha(context)
            bake_boilerplate(context, "Alpha", "EMIT", (-1000, -1500), True)
            unsetup_alpha(context)

        bpy.data.scenes["Scene"].render.engine = render_engine

        if context.scene.ez_bake_auto_refresh:
            refresh_textures(context)

        return {'FINISHED'}

def refresh_textures(context):
    for img in bpy.data.images:
        if context.object.name in img.filepath:
            img.reload()

    
def setup_color(context):
    for material_slot in context.object.material_slots:
        mat = material_slot.material
        output = next(x for x in mat.node_tree.nodes if x.bl_idname == "ShaderNodeOutputMaterial")
        bsdf = next(x for x in mat.node_tree.nodes if x.bl_idname == "ShaderNodeBsdfPrincipled")
        metallic_link = [x for x in mat.node_tree.links if x.to_node == bsdf and x.to_socket.identifier == 'Metallic']
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
        output = next(x for x in mat.node_tree.nodes if x.bl_idname == "ShaderNodeOutputMaterial")
        bsdf = next(x for x in mat.node_tree.nodes if x.bl_idname == "ShaderNodeBsdfPrincipled")
        metallic_temp = next(x for x in mat.node_tree.nodes if x.name == 'EZBake_MetallicTemp')
        if metallic_temp.bl_idname == 'ShaderNodeValue':
            # copy value back to bsdf
            bsdf.inputs['Metallic'].default_value = metallic_temp.outputs[0].default_value
            mat.node_tree.nodes.remove(metallic_temp)
        elif metallic_temp.bl_idname == 'NodeReroute':
            # plug reroute back in
            metallic_link = next(x for x in mat.node_tree.links if x.to_socket == metallic_temp.inputs[0])
            mat.node_tree.links.new(metallic_link.from_socket, bsdf.inputs['Metallic'])
            mat.node_tree.links.remove(metallic_link)
            mat.node_tree.nodes.remove(metallic_temp)
        else:
            print("fuck")
            
def setup_metallic(context):
    for material_slot in context.object.material_slots:
        mat = material_slot.material
        output = next(x for x in mat.node_tree.nodes if x.bl_idname == "ShaderNodeOutputMaterial")
        bsdf = next(x for x in mat.node_tree.nodes if x.bl_idname == "ShaderNodeBsdfPrincipled")
        metallic_link = [x for x in mat.node_tree.links if x.to_node == bsdf and x.to_socket.identifier == 'Metallic']
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
            mat.node_tree.links.new(metallic_link.from_socket, output.inputs[0])
            
def unsetup_metallic(context):
    for material_slot in context.object.material_slots:
        mat = material_slot.material
        output = next(x for x in mat.node_tree.nodes if x.bl_idname == "ShaderNodeOutputMaterial")
        bsdf = next(x for x in mat.node_tree.nodes if x.bl_idname == "ShaderNodeBsdfPrincipled")
        metallic_temp = [x for x in mat.node_tree.nodes if x.name == 'EZBake_MetallicTemp']
        if len(metallic_temp) == 1:
            metallic_temp = metallic_temp[0]
            # copy value back to bsdf
            mat.node_tree.nodes.remove(metallic_temp)
            mat.node_tree.links.new(bsdf.outputs[0], output.inputs[0])
        else:
            # plug reroute back in
            metallic_link = next(x for x in mat.node_tree.links if x.to_socket == output.inputs[0])
            mat.node_tree.links.remove(metallic_link)
            mat.node_tree.links.new(bsdf.outputs[0], output.inputs[0])

def setup_alpha(context):
    for material_slot in context.object.material_slots:
        mat = material_slot.material
        output = next(x for x in mat.node_tree.nodes if x.bl_idname == "ShaderNodeOutputMaterial")
        bsdf = next(x for x in mat.node_tree.nodes if x.bl_idname == "ShaderNodeBsdfPrincipled")
        alpha_link = [x for x in mat.node_tree.links if x.to_node == bsdf and x.to_socket.identifier == 'Alpha']
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
        output = next(x for x in mat.node_tree.nodes if x.bl_idname == "ShaderNodeOutputMaterial")
        bsdf = next(x for x in mat.node_tree.nodes if x.bl_idname == "ShaderNodeBsdfPrincipled")
        alpha_temp = [x for x in mat.node_tree.nodes if x.name == 'EZBake_AlphaTemp']
        if len(alpha_temp) == 1:
            alpha_temp = alpha_temp[0]
            # copy value back to bsdf
            mat.node_tree.nodes.remove(alpha_temp)
            mat.node_tree.links.new(bsdf.outputs[0], output.inputs[0])
        else:
            # plug reroute back in
            alpha_link = next(x for x in mat.node_tree.links if x.to_socket == output.inputs[0])
            mat.node_tree.links.remove(alpha_link)
            mat.node_tree.links.new(bsdf.outputs[0], output.inputs[0])




def bake_boilerplate(context, name, type, node_location, non_color):
    image_name = f'{context.object.name}_{name}'
    resolution = context.object.ez_bake_resolution

    image = bpy.data.images.get(image_name)
    if image is None:
        bpy.ops.image.new(name=image_name, width=resolution, height=resolution, alpha=False)
        image = bpy.data.images[image_name]
        
    if non_color:
        image.colorspace_settings.name = 'Non-Color'
    
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
        table = {
            'JPG': ['jpg', 'JPEG'],
            'PNG': ['png', 'PNG'],
        }
        image.filepath_raw = f'//Textures/{image_name}.{table[context.object.ez_bake_file_format][0]}'
        image.file_format = table[context.object.ez_bake_file_format][1]
        image.save()
    # bpy.ops.object.bake('INVOKE_DEFAULT', type=type)
    context.scene.cycles.samples = original_samples
    
    # clean up nodes
    for material_slot in context.object.material_slots:
        mat = material_slot.material

        node_name = f'EZBake_{name}'
        node = mat.node_tree.nodes.get(node_name)
        if node is not None:
            mat.node_tree.nodes.remove(node)
    
    

def register():
    bpy.utils.register_class(EzBakePanel)
    bpy.utils.register_class(EzBake)
    bpy.types.Object.ez_bake_resolution = bpy.props.IntProperty(name = "Resolution", default=1024)
    bpy.types.Object.ez_bake_save_to_file = bpy.props.BoolProperty(name = "Save to file", default = True)
    bpy.types.Object.ez_bake_file_format = bpy.props.EnumProperty(items = [('JPG', 'JPG', 'JPG'), ('PNG', 'PNG', 'PNG')], name = "File format", default='JPG')
    bpy.types.Object.ez_bake_samples = bpy.props.IntProperty(name = "Samples", default = 32)
    bpy.types.Object.ez_bake_color = bpy.props.BoolProperty(name = "Color", default = True)
    bpy.types.Object.ez_bake_roughness = bpy.props.BoolProperty(name = "Roughness", default = True)
    bpy.types.Object.ez_bake_metallic = bpy.props.BoolProperty(name = "Metallic", default = True)
    bpy.types.Object.ez_bake_emission = bpy.props.BoolProperty(name = "Emission", default = True)
    bpy.types.Object.ez_bake_normal = bpy.props.BoolProperty(name = "Normal", default = True)
    bpy.types.Object.ez_bake_alpha = bpy.props.BoolProperty(name = "Alpha", default = True)
    bpy.types.Scene.ez_bake_auto_refresh = bpy.props.BoolProperty(name = "Auto refresh textures", default = True)
def unregister():
    bpy.utils.unregister_class(EzBakePanel)
    bpy.utils.unregister_class(EzBake)

if __name__ == "__main__":
    register()
