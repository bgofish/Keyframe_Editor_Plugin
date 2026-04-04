from __future__ import annotations
import json
import tempfile
import os
import lichtfeld as lf

class KeyframeEditorPanel(lf.ui.Panel):
    id    = "keyframe_editor.panel"
    label = "Keyframe Editor"
    space = lf.ui.PanelSpace.MAIN_PANEL_TAB
    order = 200

    @classmethod
    def poll(cls, context) -> bool:
        return True

    def __init__(self):
        self._status = ""

    def draw(self, ui):
        ui.heading("Keyframe Editor")
        ui.label("Hello")
