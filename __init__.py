from . import preferences
from . import contributing_objects
from . import utils
import mathutils
import bpy

bl_info = {
    "name": "EZ Bake",
    "description": "Automate and streamline the baking process",
    "version": (0, 1),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > EZ Bake",
    "category": "Object",
}

# TODO: convert resolution to enum with option 512, 1024, 2048, 4096, 8192
#       rearrange UI
#       make prefs work properly, sort out packing

class EzBakePanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_ez_bake"
    bl_label = "EZ Bake"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EZ Bake"
    bl_context = "objectmode"

    def draw(self, context):
        # Prevent errors when active object doesn't exist
        if context.active_object is None:
            return

        layout = self.layout
        if context.scene.demo.total is not 0:
            layout.progress(factor = context.scene.demo.progress / context.scene.demo.total, type = "BAR", text = f'{context.scene.demo.progress} / {context.scene.demo.total}')
        layout.prop(context.object, "ez_bake_resolution")
        layout.prop(context.object, "ez_bake_save_to_file")
        format = layout.row()
        format.prop(context.object, "ez_bake_file_format", expand=True)
        format.active = context.object.ez_bake_save_to_file
        layout.prop(context.object, "ez_bake_samples")
        layout.operator("object.ez_bake")

        header, panel = layout.panel("Selected to Active")
        header = header.row()
        header.prop(context.object, "ez_bake_use_contributing_objects", text="")
        header.label(text="Selected to active")
        header.operator("ez_bake.add_contributing_object", text="", icon='ADD')
        if panel:
            for index, obj in enumerate(context.object.ez_bake_contributing_objects):
                row = panel.row(align=True)
                row.prop(obj, "object", text="")
                row.operator("ez_bake.remove_contributing_object", text="", icon='REMOVE').index = index
        
        header, panel = layout.panel("Maps")
        header.label(text="Maps")
        if panel:
            panel = panel.grid_flow(columns=2, row_major=True)
            panel.prop(context.object, "ez_bake_color")
            panel.prop(context.object, "ez_bake_roughness")
            panel.prop(context.object, "ez_bake_metallic")
            panel.prop(context.object, "ez_bake_normal")
            panel.prop(context.object, "ez_bake_emission")
            panel.prop(context.object, "ez_bake_alpha")

        layout.prop(context.scene, "ez_bake_auto_refresh")


class EzBake(bpy.types.Operator):
    bl_label = "EZ Bake"
    bl_idname = "object.ez_bake"
    bl_options = {'REGISTER', 'UNDO'}

    _timer = None
    original_render_engine = bpy.props.StringProperty()
    original_cycles_samples = bpy.props.IntProperty()

    def modal(self, context, event):
        if context.scene.demo.progress == context.scene.demo.total:
            # Cleanup
            context.scene.render.engine = self.original_render_engine
            context.scene.cycles.samples = self.original_cycles_samples

            if context.scene.ez_bake_auto_refresh:
                refresh_textures(context)

            self.cancel(context)
            return {"FINISHED"}

        if event.type in {"RIGHTMOUSE", "ESC"}:
            self.cancel(context)
            return {"CANCELLED"}

        return {"PASS_THROUGH"}

    def cancel(self, context):
        context.window_manager.event_timer_remove(self._timer)
        self._timer = None

        context.scene.demo.progress = 0
        context.scene.demo.total = 0

    def execute(self, context):
        # Check if all materials are ok to bake
        for material_slot in context.object.material_slots:
            mat = material_slot.material
            if len([x for x in mat.node_tree.nodes if x.bl_idname == "ShaderNodeBsdfPrincipled"]) != 1:
                self.report({"ERROR"}, f'{len([x for x in mat.node_tree.nodes if x.bl_idname == "ShaderNodeBsdfPrincipled"])} BSDFs found in material {mat.name}')
                return {'CANCELLED'}

        # General baking setup

        self.original_render_engine = context.scene.render.engine
        context.scene.render.engine = 'CYCLES'

        self.original_cycles_samples = context.scene.cycles.samples
        context.scene.cycles.samples = context.object.ez_bake_samples

        context.scene.render.bake.use_pass_direct = False
        context.scene.render.bake.use_pass_indirect = False
        context.scene.cycles.use_denoising = True
        context.scene.render.bake.use_clear = True
        context.scene.render.bake.use_selected_to_active = False

        macro = utils.get_macro()

        if context.object.ez_bake_color:
            utils.add_bake(macro, context, "Color", "DIFFUSE")
        if context.object.ez_bake_roughness:
            utils.add_bake(macro, context, "Roughness", "ROUGHNESS", non_color=True)
        if context.object.ez_bake_metallic:
            utils.add_bake(macro, context, "Metallic", "EMIT", non_color=True)
        if context.object.ez_bake_normal:
            utils.add_bake(macro, context, "Normal", "NORMAL", non_color=True)
        if context.object.ez_bake_emission:
            utils.add_bake(macro, context, "Emission", "EMIT")
        if context.object.ez_bake_alpha:
            utils.add_bake(macro, context, "Alpha", "EMIT", non_color=True)

        if context.object.ez_bake_use_contributing_objects:
            # Contributing objects setup
            macro.define("OBJECT_OT_ez_bake_contrib_setup")

            if context.object.ez_bake_color:
                utils.add_bake(macro, context, "Color", "DIFFUSE")
            if context.object.ez_bake_roughness:
                utils.add_bake(macro, context, "Roughness", "ROUGHNESS", non_color=True)
            if context.object.ez_bake_metallic:
                utils.add_bake(macro, context, "Metallic", "EMIT", non_color=True)
            if context.object.ez_bake_normal:
                utils.add_bake(macro, context, "Normal", "NORMAL", non_color=True)
            if context.object.ez_bake_emission:
                utils.add_bake(macro, context, "Emission", "EMIT")
            if context.object.ez_bake_alpha:
                utils.add_bake(macro, context, "Alpha", "EMIT", non_color=True)

            macro.define("OBJECT_OT_ez_bake_contrib_cleanup")


        context.scene.demo.total = macro.steps

        bpy.ops.object.ez_bake_macro("INVOKE_DEFAULT")

        self._timer = context.window_manager.event_timer_add(0.1, window=context.window)
        context.window_manager.modal_handler_add(self)

        return {"RUNNING_MODAL"}

def refresh_textures(context):
    for img in bpy.data.images:
        if context.object.name in img.filepath:
            img.reload()


def register():
    preferences.register()
    contributing_objects.register()
    utils.register()
    bpy.utils.register_class(EzBakePanel)
    bpy.utils.register_class(EzBake)

    bpy.types.Object.ez_bake_resolution = bpy.props.IntProperty(
        name="Resolution", default=2048)
    bpy.types.Object.ez_bake_save_to_file = bpy.props.BoolProperty(
        name="Save to file", default=True)
    bpy.types.Object.ez_bake_file_format = bpy.props.EnumProperty(items=[(
        'JPG', 'JPG', 'JPG'), ('PNG', 'PNG', 'PNG')], name="File format", default='JPG')
    bpy.types.Object.ez_bake_samples = bpy.props.IntProperty(
        name="Samples", default=8)
    bpy.types.Object.ez_bake_color = bpy.props.BoolProperty(
        name="Color", default=True)
    bpy.types.Object.ez_bake_roughness = bpy.props.BoolProperty(
        name="Roughness", default=True)
    bpy.types.Object.ez_bake_metallic = bpy.props.BoolProperty(
        name="Metallic", default=True)
    bpy.types.Object.ez_bake_normal = bpy.props.BoolProperty(
        name="Normal", default=True)
    bpy.types.Object.ez_bake_emission = bpy.props.BoolProperty(
        name="Emission", default=False)
    bpy.types.Object.ez_bake_alpha = bpy.props.BoolProperty(
        name="Alpha", default=False)
    bpy.types.Scene.ez_bake_auto_refresh = bpy.props.BoolProperty(
        name="Auto refresh textures", default=True)



def unregister():
    preferences.unregister()
    contributing_objects.unregister()
    utils.unregister()
    bpy.utils.unregister_class(EzBakePanel)
    bpy.utils.unregister_class(EzBake)

if __name__ == "__main__":
    register()
