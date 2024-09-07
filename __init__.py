from . import preferences
from . import overlay_objects
from . import utils
from . import props
from . import panel
from . import operator
from . import macro

bl_info = {
    "name": "EZ Bake",
    "description": "Automate and streamline the baking process",
    "version": (0, 1),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > EZ Bake",
    "category": "Object",
}


def register():
    preferences.register()
    overlay_objects.register()
    utils.register()
    props.register()
    panel.register()
    operator.register()
    macro.register()


def unregister():
    preferences.unregister()
    overlay_objects.unregister()
    utils.unregister()
    props.unregister()
    panel.unregister()
    operator.unregister()
    macro.unregister()


if __name__ == "__main__":
    register()
