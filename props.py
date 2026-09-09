import bpy

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
    
    file_format: bpy.props.EnumProperty(
        items=[
            ('JPG', 'JPG', 'JPG File format'),
            ('PNG', 'PNG', 'PNG File format')],
        name="File format", description="File format to use for the baked texture",
        default='JPG')
    
    save_path: bpy.props.StringProperty(name="Save Path", description="Folder to save baked images to. Use // for relative path, leave empty to disable", default="")

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
        type=EzBakeOverlayLayer)
        
    setup_update_baked_material: bpy.props.BoolProperty(name="Setup/Update Baked Material", default=True)

class EzBakeOverlayLayer(bpy.types.PropertyGroup):
    enabled: bpy.props.BoolProperty(name="Enabled", default=True)
    type: bpy.props.EnumProperty(items=[("Object", "Object", "Object", "OBJECT_DATA", 0), ("Collection", "Collection", "Collection", "OUTLINER_COLLECTION", 1)])
    object: bpy.props.PointerProperty(type=bpy.types.Object)
    collection: bpy.props.PointerProperty(type=bpy.types.Collection)


def register():
    bpy.utils.register_class(EzBakeObjectProps)
    bpy.types.Object.ez_bake_object_props = bpy.props.PointerProperty(type=EzBakeObjectProps)

    bpy.utils.register_class(EzBakeOverlayLayer)

def unregister():
    bpy.utils.unregister_class(EzBakeObjectProps)

    bpy.utils.unregister_class(EzBakeOverlayLayer)
