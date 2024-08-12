import bpy

# Single object reference
class EzBakeContributingObject(bpy.types.PropertyGroup):
    object: bpy.props.PointerProperty(name="Object", type=bpy.types.Object)

# Add an object to the list
class OBJECT_OT_ez_bake_add_contributing_object(bpy.types.Operator):
    bl_idname = "ez_bake.add_contributing_object"
    bl_label = "Add Object"

    def execute(self, context):
        context.object.ez_bake_contributing_objects.add()
        return {'FINISHED'}

# Remove an object from the list
class OBJECT_OT_ez_bake_remove_contributing_object(bpy.types.Operator):
    bl_idname = "ez_bake.remove_contributing_object"
    bl_label = "Remove Object"

    index: bpy.props.IntProperty()

    def execute(self, context):
        context.object.ez_bake_contributing_objects.remove(self.index)
        
        return {'FINISHED'}

def register():
    bpy.utils.register_class(EzBakeContributingObject)
    bpy.utils.register_class(OBJECT_OT_ez_bake_add_contributing_object)
    bpy.utils.register_class(OBJECT_OT_ez_bake_remove_contributing_object)

    bpy.types.Object.ez_bake_contributing_objects = bpy.props.CollectionProperty(type=EzBakeContributingObject)
    bpy.types.Object.ez_bake_use_contributing_objects = bpy.props.BoolProperty(name="Use contributing objects", default=False)

def unregister():
    bpy.utils.unregister_class(EzBakeContributingObject)
    bpy.utils.unregister_class(OBJECT_OT_ez_bake_add_contributing_object)
    bpy.utils.unregister_class(OBJECT_OT_ez_bake_remove_contributing_object)
