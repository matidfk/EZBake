from . import preferences
from . import contributing_objects
from . import utils
import bpy

bl_info = {
    "name": "EZ Bake",
    "description": "Automate and streamline the baking process",
    "version": (0, 1),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > EZ Bake",
    "category": "Object",
}


class OBJECT_PT_ez_bake(bpy.types.Panel):
    bl_label = "EZ Bake"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EZ Bake"
    bl_context = "objectmode"

    def draw(self, context):
        obj = context.object
        # Prevent errors when active object doesn't exist
        if obj is None:
            return

        layout = self.layout
        layout.alignment = 'RIGHT'

        layout.template_shaderfx()

        # OPERATOR BUTTON
        box = layout.row()
        box.scale_y = 2.0
        box.operator("object.ez_bake")

        # PROGRESS BAR
        progress = context.scene.ez_bake_progress
        if not progress.is_finished():
            layout.progress(type='BAR',
                            factor=progress.get_progress_fac(),
                            text=progress.get_progress_string())
            layout.active = False

        # MAPS
        header, panel = layout.panel("ez_bake_maps")
        header.label(text="Maps")
        if panel:
            panel = panel.grid_flow(columns=2, row_major=True)
            panel.prop(obj, "ez_bake_color")
            panel.prop(obj, "ez_bake_roughness")
            panel.prop(obj, "ez_bake_metallic")
            panel.prop(obj, "ez_bake_normal")
            panel.prop(obj, "ez_bake_emission")
            panel.prop(obj, "ez_bake_alpha")

        # SAMPLES
        row = layout.row()
        row.label(text="Samples")
        row.prop(obj, "ez_bake_samples", text="")
        # RESOLUTION
        row = layout.row()
        row.label(text="Resolution")
        row.prop(obj, "ez_bake_resolution", text="")
        # FILE FORMAT
        layout.prop(obj, "ez_bake_file_format", expand=True)
        # UV MAP
        row = layout.row()
        row.label(text="UV Map")
        row.prop_search(obj, "ez_bake_uv_map",
                        obj.data, "uv_layers", icon='GROUP_UVS', text="")

        # CONTRIBUTING OBJECTS
        header, panel = layout.panel("ez_bake_contributing_objects",
                                     default_closed=True)
        header = header.row()
        header.prop(obj, "ez_bake_use_contributing_objects", text="")
        header.label(text="Contributing objects")
        header.operator("ez_bake.add_contributing_object", text="", icon='ADD')
        if panel:
            if len(obj.ez_bake_contributing_objects) == 0:
                panel.label(text="No objects added")
            else:
                for index, c_obj in enumerate(obj.ez_bake_contributing_objects):
                    row = panel.row(align=True)
                    row.prop(c_obj, "object", text="")
                    row.operator("ez_bake.remove_contributing_object",
                                 text="", icon='REMOVE').index = index

        # AUTO REFRESH
        layout.prop(context.scene, "ez_bake_auto_refresh")


class OBJECT_OT_ez_bake(bpy.types.Operator):
    bl_label = "EZ Bake"
    bl_idname = "object.ez_bake"
    bl_options = {'REGISTER', 'UNDO'}

    _timer = None
    original_render_engine = bpy.props.StringProperty()
    original_cycles_samples = bpy.props.IntProperty()

    def modal(self, context, event):
        if context.scene.ez_bake_progress.is_finished():
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

        context.scene.ez_bake_progress.reset()

    def execute(self, context):
        obj = context.object

        # Check if all materials are ok to bake
        for material_slot in obj.material_slots:
            mat = material_slot.material
            bsdf_count = len([x for x in mat.node_tree.nodes
                              if x.bl_idname == "ShaderNodeBsdfPrincipled"])
            if bsdf_count != 1:
                self.report({"ERROR"},
                            f'{bsdf_count} BSDFs found in material {mat.name}')
                return {'CANCELLED'}

        # General baking setup
        self.original_render_engine = context.scene.render.engine
        context.scene.render.engine = 'CYCLES'

        self.original_cycles_samples = context.scene.cycles.samples
        context.scene.cycles.samples = obj.ez_bake_samples

        context.scene.render.bake.use_pass_direct = False
        context.scene.render.bake.use_pass_indirect = False
        context.scene.cycles.use_denoising = True

        context.scene.ez_bake_progress.reset()

        macro = utils.get_macro()

        if obj.ez_bake_use_contributing_objects:
            macro.define("OBJECT_OT_ez_bake_contrib_setup")

        if obj.ez_bake_color:
            utils.add_bake(macro, context, "Color", "DIFFUSE")
        if obj.ez_bake_roughness:
            utils.add_bake(macro, context, "Roughness",
                           "ROUGHNESS", non_color=True)
        if obj.ez_bake_metallic:
            utils.add_bake(macro, context, "Metallic", "EMIT", non_color=True)
        if obj.ez_bake_normal:
            utils.add_bake(macro, context, "Normal", "NORMAL", non_color=True)
        if obj.ez_bake_emission:
            utils.add_bake(macro, context, "Emission", "EMIT")
        if obj.ez_bake_alpha:
            utils.add_bake(macro, context, "Alpha", "EMIT", non_color=True)


        if obj.ez_bake_use_contributing_objects:
            macro.define("OBJECT_OT_ez_bake_contrib_cleanup")

        context.scene.ez_bake_progress.total = macro.steps

        bpy.ops.object.ez_bake_macro("INVOKE_DEFAULT")

        self._timer = context.window_manager.event_timer_add(
            0.1, window=context.window)
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
    bpy.utils.register_class(OBJECT_PT_ez_bake)
    bpy.utils.register_class(OBJECT_OT_ez_bake)

    bpy.types.Object.ez_bake_resolution = bpy.props.EnumProperty(
        name="Resolution",
        items=[
            ('512', "512", "512 x 512"),
            ('1024', "1024", "1024 x 1024"),
            ('2048', "2048", "2048 x 2048"),
            ('4096', "4096", "4096 x 4096"),
            ('8192', "8192", "8192 x 8192"),
        ],
        default='2048'
    )
    bpy.types.Object.ez_bake_file_format = bpy.props.EnumProperty(
        items=[
            ('JPG', 'JPG', 'JPG File format'),
            ('PNG', 'PNG', 'PNG File format')],
        name="File format",
        description="File format to use for the baked texture",
        default='JPG')
    bpy.types.Object.ez_bake_samples = bpy.props.IntProperty(
        name="Samples",
        description="""Number of samples to use for baking.
        Lower=Faster, Higher=Less noise""",
        default=8,
        min=1)
    bpy.types.Object.ez_bake_uv_map = bpy.props.StringProperty(
        name="UV Map",
        description="UV map to use for baking",
        default="UVMap")
    bpy.types.Object.ez_bake_color = bpy.props.BoolProperty(
        name="Color",
        description="Bake the color map",
        default=True)
    bpy.types.Object.ez_bake_roughness = bpy.props.BoolProperty(
        name="Roughness",
        description="Bake the roughness map",
        default=True)
    bpy.types.Object.ez_bake_metallic = bpy.props.BoolProperty(
        name="Metallic",
        description="Bake the metallic map",
        default=True)
    bpy.types.Object.ez_bake_normal = bpy.props.BoolProperty(
        name="Normal",
        description="Bake the normal map",
        default=True)
    bpy.types.Object.ez_bake_emission = bpy.props.BoolProperty(
        name="Emission",
        description="Bake the emission map",
        default=False)
    bpy.types.Object.ez_bake_alpha = bpy.props.BoolProperty(
        name="Alpha",
        description="Bake the alpha map",
        default=False)
    bpy.types.Scene.ez_bake_auto_refresh = bpy.props.BoolProperty(
        name="Auto refresh textures",
        description="Automatically refresh all images using the baked texture",
        default=True)


def unregister():
    preferences.unregister()
    contributing_objects.unregister()
    utils.unregister()
    bpy.utils.unregister_class(OBJECT_PT_ez_bake)
    bpy.utils.unregister_class(OBJECT_OT_ez_bake)


if __name__ == "__main__":
    register()
