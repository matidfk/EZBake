import bpy

def get_current_step():
    return bpy.context.scene.ez_bake_steps.split(";")[bpy.context.scene.ez_bake_current_step]

def get_progress_factor():
    steps = len(bpy.context.scene.ez_bake_steps.split(";")) - 1.0
    return bpy.context.scene.ez_bake_current_step / steps

# Add a layer to the list
class OBJECT_OT_ez_bake_add_overlay_layer(bpy.types.Operator):
    bl_idname = "ez_bake.add_overlay_layer"
    bl_label = "Add Overlay"
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


class OBJECT_PT_ez_bake(bpy.types.Panel):
    bl_label = "EZ bake"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "EZ bake"
    bl_context = "objectmode"
    
    def draw(self, context):
        obj = context.object
        if context.scene.ez_bake_steps == "" and (obj is None or not obj.select_get()):
            self.layout.label(text="No object selected")
            return
        
        obj_props = obj.ez_bake_object_props
        layout = self.layout
        
        # PROGRESS BAR
        if context.scene.ez_bake_steps != "":
            layout.progress(type="BAR", factor=get_progress_factor(), text=get_current_step())
            layout.enabled = False
            
        else:
            row = layout.row()
            row.emboss = "PIE_MENU"
            label = row.label(icon="OBJECT_DATA", text=obj.name)
            
            
        
        # OPERATOR BUTTON
        box = layout.row()
        box.scale_y = 2.0
        box.operator("object.ez_bake")
        
        # MAPS DROPDOWN
        header, panel = layout.panel("ez_bake_maps")
        header.label(text="Maps", icon="RENDERLAYERS")
        if panel:
            panel = panel.grid_flow(columns=2, row_major=True)
            panel.prop(obj_props, "bake_color")
            panel.prop(obj_props, "bake_roughness")
            panel.prop(obj_props, "bake_metallic")
            panel.prop(obj_props, "bake_normal")
            panel.prop(obj_props, "bake_emission")
            panel.prop(obj_props, "bake_alpha")
        
        # BAKE OPTIONS
        header, panel = layout.panel("ez_bake_options")
        header.label(text="Bake options", icon="SETTINGS")
        if panel:
            # UV MAP
            row = panel.row()
            row.label(text="UV Map")
            row.prop_search(obj_props, "uv_map", obj.data, "uv_layers", icon='GROUP_UVS', text="")
            
            row = panel.row()
            row.label(text="Setup/Update baked material")
            row.prop(obj_props, "setup_update_baked_material", text="")
            
            row = panel.row()
            row.label(text="Extrusion")
            row.prop(context.scene.render.bake, "cage_extrusion", text="")
            
        # FORMAT OPTIONS
        header, panel = layout.panel("ez_bake_format_options")
        header.label(text="Format options", icon="FILE_IMAGE")
        if panel:
            # SAMPLES
            row = panel.row()
            row.label(text="Samples")
            row.prop(obj_props, "samples", text="")
            # RESOLUTION
            row = panel.row()
            row.label(text="Resolution")
            row.prop(obj_props, "resolution", text="")
            # FILE FORMAT
            row = panel.row()
            row.prop(obj_props, "file_format", expand=True)
            # SAVE PATH
            row = panel.row()
            row.label(text="Save path")
            row.prop(obj_props, "save_path", text="")
        
        # OVERLAYS
        header, panel = layout.panel("ez_bake_overlays")
        header.label(text="Overlays", icon="OVERLAY")
        header.prop(obj_props, "use_overlays", text="")
        if panel:
            if not obj_props.use_overlays:
                panel.active = False
            if len(obj_props.overlay_layers) == 0:
                panel.label(text="No overlays added")
            else:
                for layer_index, layer in enumerate(obj_props.overlay_layers):
                    row = panel.row()
#                    row.label(text=f"{layer_index}")
                    row = row.row()
                                
                    row.prop(layer, "type", expand=True, icon_only=True)
                    if layer.type == "Collection":
                        row.prop(layer, "collection", text="")
                    else:
                        row.prop(layer, "object", text="")
                    row.operator("ez_bake.remove_overlay_layer", icon="X", text="").index = layer_index
                    
            
            panel.operator("ez_bake.add_overlay_layer", icon="ADD")





def register():
    bpy.utils.register_class(OBJECT_PT_ez_bake)

    bpy.utils.register_class(OBJECT_OT_ez_bake_add_overlay_layer)
    bpy.utils.register_class(OBJECT_OT_ez_bake_remove_overlay_layer)

def unregister():
    bpy.utils.unregister_class(OBJECT_PT_ez_bake)

    bpy.utils.unregister_class(OBJECT_OT_ez_bake_add_overlay_layer)
    bpy.utils.unregister_class(OBJECT_OT_ez_bake_remove_overlay_layer)

