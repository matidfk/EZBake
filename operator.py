import bpy
from . import utils
from . import macro


class OBJECT_OT_ez_bake(bpy.types.Operator):
    bl_label = "EZ Bake"
    bl_idname = "object.ez_bake"
    bl_options = {'REGISTER', 'UNDO'}

    _timer = None
    original_render_engine = bpy.props.StringProperty()
    original_cycles_samples = bpy.props.IntProperty()

    def modal(self, context, event):
        if context.scene.ez_bake_progress.is_finished():
            # Restore render settings
            context.scene.render.engine = self.original_render_engine
            context.scene.cycles.samples = self.original_cycles_samples

            utils.setup_materials(context)

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

        self.check_materials(context)

        self.general_bake_setup(context)

        context.scene.ez_bake_progress.reset()

        _macro = macro.get_macro(context)

        # if obj.ez_bake_use_contributing_objects:
        #     macro.define("OBJECT_OT_ez_bake_contrib_setup")
        #
        # if obj.ez_bake_use_contributing_objects:
        #     macro.define("OBJECT_OT_ez_bake_contrib_cleanup")

        context.scene.ez_bake_progress.total = _macro.steps

        bpy.ops.object.ez_bake_macro("INVOKE_DEFAULT")

        self._timer = context.window_manager.event_timer_add(
            0.1, window=context.window)
        context.window_manager.modal_handler_add(self)

        return {"RUNNING_MODAL"}

    def check_materials(self, context):
        for material in utils.get_materials(context.object):
            if not utils.check_material(material):
                self.report({"WARNING"}, f'Material {material.name} has none or multiple BSDFs, skipping')

    def general_bake_setup(self, context):
        self.original_render_engine = context.scene.render.engine
        context.scene.render.engine = 'CYCLES'

        self.original_cycles_samples = context.scene.cycles.samples
        context.scene.cycles.samples = context.object.ez_bake_object_props.samples

        context.scene.render.bake.use_pass_direct = False
        context.scene.render.bake.use_pass_indirect = False
        context.scene.cycles.use_denoising = False

        context.scene.render.bake.use_selected_to_active = False
        context.scene.render.bake.use_clear = True


def register():
    bpy.utils.register_class(OBJECT_OT_ez_bake)


def unregister():
    bpy.utils.unregister_class(OBJECT_OT_ez_bake)
