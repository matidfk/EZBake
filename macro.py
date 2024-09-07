import bpy
from . import utils


# Thank you Andrew Chinery https://blender.stackexchange.com/a/322063
def get_macro(context):
    # redefine the class to clear any previous steps assigned to the macro
    class OBJECT_OT_ez_bake_macro(bpy.types.Macro):
        bl_idname = "object.ez_bake_macro"
        bl_label = "Bake Macro"
        bl_options = {"INTERNAL", "MACRO"}

        steps = 0

    # unregister any previous macro
    if hasattr(bpy.types, "OBJECT_OT_ez_bake_macro"):
        bpy.utils.unregister_class(bpy.types.OBJECT_OT_ez_bake_macro)

    bpy.utils.register_class(OBJECT_OT_ez_bake_macro)
    macro = OBJECT_OT_ez_bake_macro

    for obj in context.selected_objects:
        macro.define("OBJECT_OT_ez_bake_select").properties.object_name = obj.name

        obj_props = obj.ez_bake_object_props
        if obj_props.bake_color:
            add_bake(macro, context, "Color", "DIFFUSE")
        if obj_props.bake_roughness:
            add_bake(macro, context, "Roughness", "ROUGHNESS", non_color=True)
        if obj_props.bake_metallic:
            add_bake(macro, context, "Metallic", "EMIT", non_color=True)
        if obj_props.bake_normal:
            add_bake(macro, context, "Normal", "NORMAL", non_color=True)
        if obj_props.bake_emission:
            add_bake(macro, context, "Emission", "EMIT")
        if obj_props.bake_alpha:
            add_bake(macro, context, "Alpha", "EMIT", non_color=True)

        if obj_props.use_overlays:
            for layer_index, layer in enumerate(obj_props.overlay_layers):
                # Alpha is needed
                add_bake(macro, context, "Alpha", "EMIT", non_color=True, is_overlay=True, layer_index=layer_index)

                if obj_props.bake_color:
                    add_bake(macro, context, "Color", "DIFFUSE", is_overlay=True, layer_index=layer_index)
                if obj_props.bake_roughness:
                    add_bake(macro, context, "Roughness", "ROUGHNESS", non_color=True, is_overlay=True, layer_index=layer_index)
                if obj_props.bake_metallic:
                    add_bake(macro, context, "Metallic", "EMIT", non_color=True, is_overlay=True, layer_index=layer_index)
                if obj_props.bake_normal:
                    add_bake(macro, context, "Normal", "NORMAL", non_color=True, is_overlay=True, layer_index=layer_index)
                if obj_props.bake_emission:
                    add_bake(macro, context, "Emission", "EMIT", is_overlay=True, layer_index=layer_index)

    
    macro.define("OBJECT_OT_ez_bake_restore_selection").properties.object_names = "###".join([obj.name for obj in context.selected_objects])
    
    return OBJECT_OT_ez_bake_macro


def add_bake(macro, context, map_name, map_type, non_color=False, is_overlay=False, layer_index=-1):
    # Overlay pass setup
    if is_overlay:
        overlay_setup_step = macro.define("OBJECT_OT_ez_bake_overlay_setup")
        overlay_setup_step.properties.layer_index = layer_index

    # Reroute needed nodes, setup image texture
    setup_step = macro.define("OBJECT_OT_ez_bake_setup")
    setup_step.properties.map_name = map_name
    setup_step.properties.map_type = map_type
    setup_step.properties.non_color = non_color
    setup_step.properties.is_overlay = is_overlay

    # Bake (Blender operator)
    bake_step = macro.define("OBJECT_OT_bake")
    bake_step.properties.type = map_type
    bake_step.properties.save_mode = "INTERNAL"

    # Save image
    save_step = macro.define("OBJECT_OT_ez_bake_post")
    save_step.properties.map_name = map_name
    save_step.properties.is_overlay = is_overlay

    # Overlay pass cleanup
    if is_overlay:
        overlay_cleanup_step = macro.define("OBJECT_OT_ez_bake_overlay_cleanup")

    macro.steps += 1

class OBJECT_OT_ez_bake_select(bpy.types.Operator):
    bl_idname = "object.ez_bake_select"
    bl_options = {"INTERNAL"}
    bl_label = "Select object"

    object_name: bpy.props.StringProperty()

    def execute(self, context):
        bpy.ops.object.select_all(action='DESELECT')

        obj = bpy.data.objects.get(self.object_name)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        return {'FINISHED'}

class OBJECT_OT_ez_bake_restore_selection(bpy.types.Operator):
    bl_idname = "object.ez_bake_restore_selection"
    bl_options = {"INTERNAL"}
    bl_label = "Restore original selection"

    object_names: bpy.props.StringProperty()

    def execute(self, context):
        bpy.ops.object.select_all(action='DESELECT')

        for object_name in self.object_names.split("###"):
            obj = bpy.data.objects.get(object_name)
            obj.select_set(True)
            context.view_layer.objects.active = obj
        return {'FINISHED'}

class OBJECT_OT_ez_bake_setup(bpy.types.Operator):
    bl_idname = "object.ez_bake_setup"
    bl_options = {"INTERNAL"}
    bl_label = "Setup for baking"
    map_name: bpy.props.StringProperty()
    map_type: bpy.props.StringProperty()
    non_color: bpy.props.BoolProperty()
    is_overlay: bpy.props.BoolProperty()

    def execute(self, context):
        obj = context.object
        obj_props = obj.ez_bake_object_props

        # Get image we will bake to
        image = self.get_or_create_image(context)

        for material in utils.get_materials(obj):
            utils.prepare_material(material, self.map_name)
            utils.setup_image_node(material, self.map_name, image)

        if self.is_overlay:
            bpy.ops.object.select_all(action='DESELECT')
            context.scene.objects["EZBake_overlay_temp"].select_set(True)
            obj.select_set(True)
            context.view_layer.objects.active = obj
            context.scene.render.bake.use_selected_to_active = True
            context.scene.render.bake.use_clear = False
            context.scene.render.bake.margin = 0
        else:
            context.scene.render.bake.use_selected_to_active = False
            context.scene.render.bake.use_clear = True
            context.scene.render.bake.margin = 16

        return {"FINISHED"}


    def get_or_create_image(self, context):
        obj = context.object
        obj_props = obj.ez_bake_object_props
        scene_props = context.scene.ez_bake_scene_props
        image_name = f'{obj.name}_{self.map_name}'
        if self.is_overlay:
            image_name += "_overlay"

        # Get texture image
        image = bpy.data.images.get(image_name)

        # If resolution has changed
        if image is not None and \
                (image.size[0] != int(obj_props.resolution) or image.size[1] != int(obj_props.resolution)):
            bpy.data.images.remove(image)
            image = None

        # Create new image
        if image is None:
            alpha = False
            color = (1, 0, 1, 1)

            # Contributing pass needs alpha
            if self.is_overlay:
                alpha = True
                color = (0, 0, 0, 0)

            # Color map needs alpha if pack alpha is enabled
            if scene_props.pack_alpha and self.map_name == "Color":
                alpha = True

            bpy.ops.image.new(name=image_name,
                              width=int(obj_props.resolution), height=int(obj_props.resolution),
                              alpha=alpha, color=color)

            image = bpy.data.images[image_name]

        if self.non_color:
            image.colorspace_settings.name = 'Non-Color'

        return image


class OBJECT_OT_ez_bake_post(bpy.types.Operator):
    bl_idname = "object.ez_bake_post"
    bl_options = {"INTERNAL"}
    bl_label = "Cleanup after baking"

    map_name: bpy.props.StringProperty()
    is_overlay: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        obj = context.object
        obj_props = obj.ez_bake_object_props
        scene_props = context.scene.ez_bake_scene_props
        image_name = f'{obj.name}_{self.map_name}'

        for material in utils.get_materials(obj):
            utils.restore_material(material, self.map_name)
            utils.cleanup_image_node(material, self.map_name)
    
        # OVERLAY IMAGES
        if self.is_overlay:
            # base image should already exist
            base_image = bpy.data.images[f'{obj.name}_{self.map_name}']
            overlay_image = bpy.data.images[f'{obj.name}_{self.map_name}_overlay']
            mask_image = bpy.data.images[f'{obj.name}_Alpha_overlay']

            if self.map_name == "Alpha":
                utils.overlay_images(base_image, overlay_image, mask_image)
            else: 
                utils.overlay_images(base_image, overlay_image, mask_image)
                bpy.data.images.remove(overlay_image)
            base_image.save()
            # Show new image in any open editor
            for area in context.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    area.spaces.active.image = base_image
            print(f"EZBAKE: Finished baking {base_image.name} Overlay")
        
        # ALPHA PACKING
        # only works because we always do alpha after color
        if self.map_name == "Alpha" and context.scene.ez_bake_scene_props.pack_alpha:
            utils.pack_alpha(bpy.data.images.get(
                f'{obj.name}_Color'), bpy.data.images.get(f'{obj.name}_Alpha'))
            bpy.data.images.get(f'{obj.name}_Color').save()
 
        # ORM PACKING
        # only works because we always do metallic after roughness and AO
        if self.map_name == "Metallic" and context.scene.ez_bake_scene_props.pack_orm:
            image_name = f'{obj.name}_ORM'
            image = utils.combine_orm(bpy.data.images.get(f'{obj.name}_AO'), bpy.data.images.get(
                f'{obj.name}_Roughness'), bpy.data.images.get(f'{obj.name}_Metallic'), image_name)
            self.save_image(context, image)

        # REGULAR
        self.save_image(context, bpy.data.images.get(image_name))

        context.scene.ez_bake_progress.increment()

        return {"FINISHED"}


    def save_image(self, context, image):
        scene_props = context.scene.ez_bake_scene_props

        table = {
            'JPG': ['jpg', 'JPEG'],
            'PNG': ['png', 'PNG'],
        }

        prefs = context.preferences.addons[__package__].preferences
        prefs_directory = prefs.texture_directory
        file_ext = table[scene_props.file_format][0]
        format = table[scene_props.file_format][1]

        image.filepath_raw = f'//{prefs_directory}/{image.name}.{file_ext}'
        image.file_format = format

        image.save()
        print(f"[EZBake]: Finished baking {image.name}")

        return image



def register():
    bpy.utils.register_class(OBJECT_OT_ez_bake_setup)
    bpy.utils.register_class(OBJECT_OT_ez_bake_post)
    bpy.utils.register_class(OBJECT_OT_ez_bake_select)
    bpy.utils.register_class(OBJECT_OT_ez_bake_restore_selection)

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_ez_bake_setup)
    bpy.utils.unregister_class(OBJECT_OT_ez_bake_post)
    bpy.utils.unregister_class(OBJECT_OT_ez_bake_select)
    bpy.utils.unregister_class(OBJECT_OT_ez_bake_restore_selection)
