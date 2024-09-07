import bpy
from . import overlay_objects




class EzBakeObjectProps(bpy.types.PropertyGroup):
    resolution: bpy.props.EnumProperty(
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

    samples: bpy.props.IntProperty(
        name="Samples",
        description="""Number of samples to use for baking. Lower=Faster, Higher=Less noise""",
        default=8, min=1)

    uv_map: bpy.props.StringProperty(
        name="UV Map", description="UV map to use for baking", default="UVMap")

    bake_color: bpy.props.BoolProperty(
        name="Color", description="Bake the color map", default=True)
    bake_roughness: bpy.props.BoolProperty(
        name="Roughness", description="Bake the roughness map", default=True)
    bake_metallic: bpy.props.BoolProperty(
        name="Metallic", description="Bake the metallic map", default=True)
    bake_normal: bpy.props.BoolProperty(
        name="Normal", description="Bake the normal map", default=True)
    bake_emission: bpy.props.BoolProperty(
        name="Emission", description="Bake the emission map", default=False)
    bake_alpha: bpy.props.BoolProperty(
        name="Alpha", description="Bake the alpha map", default=False)

    use_overlays: bpy.props.BoolProperty(
        name="Use overlays", default=False)
    overlay_layers: bpy.props.CollectionProperty(
        type=overlay_objects.EzBakeOverlayLayer)




class EzBakeSceneProps(bpy.types.PropertyGroup):

    file_format: bpy.props.EnumProperty(
        items=[
            ('JPG', 'JPG', 'JPG File format'),
            ('PNG', 'PNG', 'PNG File format')],
        name="File format", description="File format to use for the baked texture",
        default='JPG')
    pack_orm: bpy.props.BoolProperty(
        name="Pack ORM Map",
        description="Automatically pack AO, Roughness and Metallic into a single image",
        default=False)
    pack_alpha: bpy.props.BoolProperty(
        name="Pack Alpha",
        description="Automatically pack Alpha information into the color image",
        default=False)


def register():
    bpy.utils.register_class(EzBakeObjectProps)
    bpy.utils.register_class(EzBakeSceneProps)

    bpy.types.Object.ez_bake_object_props = bpy.props.PointerProperty(
        type=EzBakeObjectProps)
    bpy.types.Scene.ez_bake_scene_props = bpy.props.PointerProperty(
        type=EzBakeSceneProps)


def unregister():
    bpy.utils.unregister_class(EzBakeObjectProps)
    bpy.utils.unregister_class(EzBakeSceneProps)
