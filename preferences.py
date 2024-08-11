import bpy

class EzBakePreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    pack_textures: bpy.props.BoolProperty(
        name="Pack Textures",
        default=False
    )
    texture_directory: bpy.props.StringProperty(
        name="Baked texture directory (relative)",
        subtype='DIR_PATH',
        default="Textures",
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "pack_textures")
        row = layout.row()
        row.prop(self, "texture_directory")
        row.active = not self.pack_textures

def register():
    bpy.utils.register_class(EzBakePreferences)

def unregister():
    bpy.utils.unregister_class(EzBakePreferences)
