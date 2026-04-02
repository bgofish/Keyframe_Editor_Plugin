import lichtfeld as lf
from .panels.main_panel import KeyframeEditorPanel

_classes = [KeyframeEditorPanel]


def on_load():
    for cls in _classes:
        lf.register_class(cls)
    lf.log.info("keyframe_editor loaded")


def on_unload():
    for cls in reversed(_classes):
        lf.unregister_class(cls)
    lf.log.info("keyframe_editor unloaded")
