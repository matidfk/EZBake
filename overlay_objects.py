import bpy

# Single object reference
class EzBakeOverlayObject(bpy.types.PropertyGroup):
    object: bpy.props.PointerProperty(name="Object", type=bpy.types.Object)

# Layer (multiple objects)
class EzBakeOverlayLayer(bpy.types.PropertyGroup):
    enabled: bpy.props.BoolProperty(name="Enabled", default=True)
    objects: bpy.props.CollectionProperty(type=EzBakeOverlayObject)

# Add a layer to the list
class OBJECT_OT_ez_bake_add_overlay_layer(bpy.types.Operator):
    bl_idname = "ez_bake.add_overlay_layer"
    bl_label = "Add Layer"
    bl_options = {"INTERNAL", "UNDO"}

    def execute(self, context):
        context.object.ez_bake_object_props.overlay_layers.add()
        return {'FINISHED'}

# Remove a layer from the list
class OBJECT_OT_ez_bake_remove_overlay_layer(bpy.types.Operator):
    bl_idname = "ez_bake.remove_overlay_layer"
    bl_label = "Remove Layer"
    bl_options = {"INTERNAL", "UNDO"}

    index: bpy.props.IntProperty()

    def execute(self, context):
        context.object.ez_bake_object_props.overlay_layers.remove(self.index)

        return {'FINISHED'}

# Add a object to a layer
class OBJECT_OT_ez_bake_add_overlay_object(bpy.types.Operator):
    bl_idname = "ez_bake.add_overlay_object"
    bl_label = "Add Object"
    bl_options = {"INTERNAL", "UNDO"}

    layer_index: bpy.props.IntProperty()

    def execute(self, context):
        context.object.ez_bake_object_props.overlay_layers[self.layer_index].objects.add()
        return {'FINISHED'}

# Remove an object from a layer
class OBJECT_OT_ez_bake_remove_overlay_object(bpy.types.Operator):
    bl_idname = "ez_bake.remove_overlay_object"
    bl_label = "Remove Object"
    bl_options = {"INTERNAL", "UNDO"}

    layer_index: bpy.props.IntProperty()
    object_index: bpy.props.IntProperty()

    def execute(self, context):
        context.object.ez_bake_object_props.overlay_layers[self.layer_index].objects.remove(self.object_index)
        return {'FINISHED'}

def register():
    bpy.utils.register_class(EzBakeOverlayObject)
    bpy.utils.register_class(EzBakeOverlayLayer)
    bpy.utils.register_class(OBJECT_OT_ez_bake_add_overlay_layer)
    bpy.utils.register_class(OBJECT_OT_ez_bake_remove_overlay_layer)
    bpy.utils.register_class(OBJECT_OT_ez_bake_add_overlay_object)
    bpy.utils.register_class(OBJECT_OT_ez_bake_remove_overlay_object)


def unregister():
    bpy.utils.unregister_class(EzBakeOverlayObject)
    bpy.utils.unregister_class(EzBakeOverlayLayer)
    bpy.utils.unregister_class(OBJECT_OT_ez_bake_add_overlay_layer)
    bpy.utils.unregister_class(OBJECT_OT_ez_bake_remove_overlay_layer)
    bpy.utils.unregister_class(OBJECT_OT_ez_bake_add_overlay_object)
    bpy.utils.unregister_class(OBJECT_OT_ez_bake_remove_overlay_object)
