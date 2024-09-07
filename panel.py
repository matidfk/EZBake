import bpy


class OBJECT_PT_ez_bake(bpy.types.Panel):
    bl_label = "EZ Bake"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EZ Bake"
    bl_context = "objectmode"

    @classmethod
    def poll(cls, context):
        return (context.object is not None)

    def draw(self, context):
        obj = context.object
        # Prevent errors when active object doesn't exist
        if obj is None:
            return

        obj_props = obj.ez_bake_object_props
        scene_props = context.scene.ez_bake_scene_props

        layout = self.layout
        layout.alignment = 'RIGHT'

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
            panel.prop(obj_props, "bake_color")
            panel.prop(obj_props, "bake_roughness")
            panel.prop(obj_props, "bake_metallic")
            panel.prop(obj_props, "bake_normal")
            panel.prop(obj_props, "bake_emission")
            panel.prop(obj_props, "bake_alpha")


        # SAMPLES
        row = layout.row()
        row.label(text="Samples")
        row.prop(obj_props, "samples", text="")
        # RESOLUTION
        row = layout.row()
        row.label(text="Resolution")
        row.prop(obj_props, "resolution", text="")
        # FILE FORMAT
        layout.prop(scene_props, "file_format", expand=True)
        # UV MAP
        row = layout.row()
        row.label(text="UV Map")
        row.prop_search(obj_props, "uv_map",
                        obj.data, "uv_layers", icon='GROUP_UVS', text="")

        # OVERLAY LAYERS
        header, panel = layout.panel("ez_bake_overlay_layers",
                                     default_closed=True)
        header = header.row()
        header.prop(obj_props, "use_overlays", text="")
        header.label(text=f"Overlays ({len(obj_props.overlay_layers)})")
        if panel:
            if len(obj_props.overlay_layers) == 0:
                panel.label(text="No layers added")
            else:
                for layer_index, layer in enumerate(obj_props.overlay_layers):
                    layer_row = panel.column(align=True)
            
                    layer_header, layer_panel = layer_row.panel(f"ez_bake_overlay_layer[{layer_index}]")
                    split = layer_header.split(factor = 0.02)
                    split.separator()
                    layer_header = split.row(align=True)
                    layer_header.prop(layer, "enabled", text="")
                    layer_header.label(text=f"Layer {layer_index} ({len(layer.objects)})")
                    layer_header.operator("ez_bake.remove_overlay_layer",
                                 text="", icon='X').index = layer_index
                    if layer_panel:
                        if len(layer.objects) == 0:
                            layer_panel.label(text="No objects added")
                        else:
                            for object_index, object in enumerate(layer.objects):
                                split = layer_panel.split(factor=0.2, align=True)
                                split.separator()
                                object_row = split.row(align=True)
                                object_row.prop(object, "object", text="", expand=True)
                                op = object_row.operator("ez_bake.remove_overlay_object",
                                             text="", icon='X')
                                op.layer_index = layer_index
                                op.object_index = object_index

                        panel.operator("ez_bake.add_overlay_object", icon='ADD').layer_index = layer_index


            panel.operator("ez_bake.add_overlay_layer", icon='ADD')

        layout.separator(type='LINE')
        layout.prop(scene_props, "pack_orm")
        layout.prop(scene_props, "pack_alpha")


def register():
    bpy.utils.register_class(OBJECT_PT_ez_bake)


def unregister():
    bpy.utils.unregister_class(OBJECT_PT_ez_bake)
