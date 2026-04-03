"""
Keyframe Editor Panel - FULL EDIT VERSION
All 9 fields editable via save→edit→reload JSON camera path.
"""
from __future__ import annotations
import json
import tempfile
import os
import lichtfeld as lf

_FLOAT_COLS = ["time", "pos_x", "pos_y", "pos_z", "rot_x", "rot_y", "rot_z", "rot_w", "fov_mm"]
_EDIT_COLS  = _FLOAT_COLS  # all fields now editable

_SPEED_PRESETS = {
    "time":   [10.0, 1.0, 0.1],
    "fov_mm": [10.0, 1.0, 0.1],
    "pos_x":  [10.0,  1, 0.01],
    "pos_y":  [10.0,  1, 0.01],
    "pos_z":  [10.0,  1, 0.01],
    "rot_x":  [0.1, 0.01, 0.001],
    "rot_y":  [0.1, 0.01, 0.001],
    "rot_z":  [0.1, 0.01, 0.001],
    "rot_w":  [0.1, 0.01, 0.001],
}
_SPEED_LABELS = ["Fast", "Med", "Fine"]

_DRAG_W    = 100   # narrower slider to make room
_VAL_W     = 100   # manual input box
_LIVE_W    = 100    # live value label width

# (col, label, min, max)  — all editable now
_EDITOR_FIELDS = [
    ("time",   "Time",    0.0,    3600.0),
    ("fov_mm", "FoV mm",  1.0,    300.0),
    ("pos_x",  "Pos X",   -500.0, 500.0),
    ("pos_y",  "Pos Y",   -500.0, 500.0),
    ("pos_z",  "Pos Z",   -500.0, 500.0),
    ("rot_x",  "Rot X",   -1.0,   1.0),
    ("rot_y",  "Rot Y",   -1.0,   1.0),
    ("rot_z",  "Rot Z",   -1.0,   1.0),
    ("rot_w",  "Rot W",   -1.0,   1.0),
]

_GROUP_BEFORE = {
    "time":   "Time & FoV",
    "pos_x":  "Position",
    "rot_x":  "Rotation (quaternion)",
}


def _get_kf_nodes() -> list:
    try:
        return [n for n in lf.get_scene().get_nodes()
                if str(n.type) == "NodeType.KEYFRAME"]
    except Exception:
        return []


def _node_to_dict(node) -> dict:
    kf  = node.keyframe_data()
    pos = kf.position
    rot = kf.rotation
    return {
        "time":  float(kf.time),
        "pos_x": float(pos[0]), "pos_y": float(pos[1]), "pos_z": float(pos[2]),
        "rot_x": float(rot[0]), "rot_y": float(rot[1]),
        "rot_z": float(rot[2]), "rot_w": float(rot[3]),
        "fov_mm":float(kf.focal_length_mm),
    }


def _load_camera_path_json() -> dict | None:
    """Save current camera path to temp file and return parsed JSON."""
    try:
        tmp = tempfile.mktemp(suffix=".json")
        lf.ui.save_camera_path(tmp)
        with open(tmp, "r") as f:
            data = json.load(f)
        try:
            os.remove(tmp)
        except Exception:
            pass
        return data
    except Exception as e:
        print(f"[KFEditor] _load_camera_path_json failed: {e}")
        return None


def _write_all_keyframes(all_nodes: list, edits: dict) -> str:
    """
    Save camera path JSON, apply any pending edits, reload.
    edits: {nid: {col: value, ...}}
    """
    try:
        # 1. Save current state to JSON
        data = _load_camera_path_json()
        if data is None:
            return "Failed to save camera path"

        keyframes = data.get("keyframes", [])

        # 2. Sort nodes by current time to match JSON order
        nodes_sorted = sorted(all_nodes, key=lambda n: float(n.keyframe_data().time))

        if len(nodes_sorted) != len(keyframes):
            return f"Node count mismatch: {len(nodes_sorted)} nodes vs {len(keyframes)} JSON entries"

        # 3. Apply edits to JSON entries
        for i, node in enumerate(nodes_sorted):
            nid = str(node.id)
            if nid not in edits:
                continue
            ed = edits[nid]
            kf = keyframes[i]
            if "time" in ed:
                kf["time"] = float(ed["time"])
            if "fov_mm" in ed:
                kf["focal_length_mm"] = float(ed["fov_mm"])
            if any(k in ed for k in ("pos_x", "pos_y", "pos_z")):
                kf["position"] = [
                    float(ed.get("pos_x", kf["position"][0])),
                    float(ed.get("pos_y", kf["position"][1])),
                    float(ed.get("pos_z", kf["position"][2])),
                ]
            if any(k in ed for k in ("rot_x", "rot_y", "rot_z", "rot_w")):
                kf["rotation"] = [
                    float(ed.get("rot_x", kf["rotation"][0])),
                    float(ed.get("rot_y", kf["rotation"][1])),
                    float(ed.get("rot_z", kf["rotation"][2])),
                    float(ed.get("rot_w", kf["rotation"][3])),
                ]

        # 4. Write modified JSON to temp file and reload
        tmp = tempfile.mktemp(suffix=".json")
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        lf.ui.load_camera_path(tmp)
        try:
            os.remove(tmp)
        except Exception:
            pass

        print(f"[KFEditor] Camera path reloaded with {len(edits)} edited keyframe(s)")
        return ""

    except Exception as exc:
        print(f"[KFEditor] _write_all_keyframes error: {exc}")
        return str(exc)


def _write_single_node(node, d: dict, all_nodes: list) -> str:
    """Write a single node by passing a one-entry edits dict."""
    return _write_all_keyframes(all_nodes, {str(node.id): d})


def _fmt(v: float) -> str:
    return f"{v:.3f}"


def _try_input_float(ui, uid, val, width):
    ui.set_next_item_width(width)
    changed, new_val = ui.input_float(uid, val)
    return changed, float(new_val)

class KeyframeEditorPanel(lf.ui.Panel):
    id    = "keyframe_editor.panel"
    label = "Keyframe Editor"
    space = lf.ui.PanelSpace.MAIN_PANEL_TAB
    order = 200
    template = ""
    style    = ""
    height_mode       = lf.ui.PanelHeightMode.FILL
    poll_dependencies = {lf.ui.PollDependency.SCENE}

    @classmethod
    def poll(cls, context) -> bool:
        return True

    def __init__(self):
        self._edits:     dict[str, dict[str, float]] = {}
        self._expanded:  str | None = None
        self._edit_buf:  dict[str, float] = {}
        self._speed_idx: dict[str, dict[str, int]] = {}
        self._status:    str = ""

    def _speed_for(self, nid, col):
        return _SPEED_PRESETS[col][self._speed_idx.get(nid, {}).get(col, 1)]

    def _cycle_speed(self, nid, col, direction):
        ns = self._speed_idx.setdefault(nid, {})
        ns[col] = (ns.get(col, 1) + direction) % len(_SPEED_PRESETS[col])

    def _toggle_editor(self, node):
        nid = str(node.id)
        if self._expanded == nid:
            self._expanded = None
            self._edit_buf = {}
        else:
            live = _node_to_dict(node)
            self._edit_buf = {**live, **self._edits.get(nid, {})}
            self._expanded = nid

    def _draw_inline_editor(self, ui, node, kf_nodes):
        nid  = str(node.id)
        live = _node_to_dict(node)

        # Safety: ensure all keys present in buf
        for k in _FLOAT_COLS:
            if k not in self._edit_buf:
                self._edit_buf[k] = live[k]
        buf = self._edit_buf

        ui.separator()
        ui.spacing()

        for col, lbl, mn, mx in _EDITOR_FIELDS:
            if col in _GROUP_BEFORE:
                ui.spacing()
                ui.label(_GROUP_BEFORE[col])
                ui.separator()

            spd_idx = self._speed_idx.get(nid, {}).get(col, 1)
            spd_lbl = _SPEED_LABELS[spd_idx]
            speed   = _SPEED_PRESETS[col][spd_idx]

            # Label
            ui.label(lbl)
            ui.same_line()

            # Manual input box — immediately after label
            val_changed, typed_val = _try_input_float(
                ui, f"##val_{nid}_{col}", buf[col], _VAL_W
            )
            if val_changed:
                buf[col] = max(mn, min(mx, typed_val))
            ui.same_line()

            # Slider
            ui.set_next_item_width(_DRAG_W)
            try:
                changed, new_val = ui.slider_float(
                    f"##drag_{nid}_{col}", buf[col], mn, mx, ""
                )
                if changed:
                    buf[col] = float(new_val)
            except Exception:
                changed, new_val = ui.drag_float(
                    f"##drag_{nid}_{col}", buf[col], speed, mn, mx
                )
                if changed:
                    buf[col] = float(new_val)
            ui.same_line()

            # [-] Med [+] on the right
            if ui.small_button(f"-##{nid}_{col}"):
                self._cycle_speed(nid, col, -1)
            ui.same_line()
            ui.label(spd_lbl)
            ui.same_line()
            if ui.small_button(f"+##{nid}_{col}"):
                self._cycle_speed(nid, col, +1)

            # Manual input box — sole value display
            val_changed, typed_val = _try_input_float(
                ui, f"##val_{nid}_{col}", buf[col], _VAL_W
            )
            if val_changed:
                buf[col] = max(mn, min(mx, typed_val))
                
        ui.spacing()
        ui.separator()
        ui.spacing()

        # Apply — write this keyframe only
        if ui.button_styled(f"Apply##{nid}", "primary"):
            e = _write_single_node(node, buf, kf_nodes)
            if e:
                self._status = f"Error: {e}"
            else:
                self._edits.pop(nid, None)
                self._status   = f"{node.name} applied."
                self._expanded = None
                self._edit_buf = {}

        ui.same_line()

        # Save draft — store without writing
        if ui.button(f"Save Draft##{nid}"):
            draft = {k: buf[k] for k in _EDIT_COLS if buf[k] != live[k]}
            self._edits[nid] = draft
            self._status   = f"{node.name} draft saved ({len(draft)} change(s))."
            self._expanded = None
            self._edit_buf = {}

        ui.same_line()

        if ui.button(f"Cancel##{nid}"):
            self._expanded = None
            self._edit_buf = {}
            self._status   = f"{node.name} edit cancelled."

        ui.spacing()
        ui.separator()

    def draw(self, ui):
        ui.heading("Keyframe Editor")

        kf_nodes = _get_kf_nodes()
        if not kf_nodes:
            ui.text_disabled("No keyframe nodes found in scene.")
            return

        if self._status:
            ui.label(self._status)

        # Toolbar
        if ui.button_styled("Apply All", "primary"):
            if self._edits:
                e = _write_all_keyframes(kf_nodes, self._edits)
                if e:
                    self._status = f"Error: {e}"
                else:
                    self._edits  = {}
                    self._status = "All changes applied."
            else:
                self._status = "No pending changes."

        if self._edits:
            ui.same_line()
            if ui.button("Discard All"):
                self._edits    = {}
                self._expanded = None
                self._edit_buf = {}
                self._status   = "All drafts discarded."

        pending = sum(len(v) for v in self._edits.values())
        ui.label(f"{len(kf_nodes)} keyframe(s)" +
                 (f"  |  {pending} unsaved change(s)" if pending else ""))
        ui.separator()

        # Column header
        ui.label("Name")
        ui.same_line()
        # ui.set_next_item_width(_SUMMARY_W)
        ui.label("Summary  (Time | Pos | Rot | FoV)")
        ui.same_line()
        ui.label("Actions")
        ui.separator()

        # Data rows
        for node in kf_nodes:
            nid     = str(node.id)
            live    = _node_to_dict(node)
            ed      = self._edits.get(nid, {})
            cur     = {**live, **ed}
            is_open = (self._expanded == nid)

            ui.label(node.name)
            ui.same_line()

            summary = (
                f"t={_fmt(cur['time'])}  "
                f"p=({_fmt(cur['pos_x'])}, {_fmt(cur['pos_y'])}, {_fmt(cur['pos_z'])})  "
                f"r=({_fmt(cur['rot_x'])}, {_fmt(cur['rot_y'])}, "
                f"{_fmt(cur['rot_z'])}, {_fmt(cur['rot_w'])})  "
                f"f={_fmt(cur['fov_mm'])}"
            )
            # ui.set_next_item_width(_SUMMARY_W)
            if ed:
                ui.label(f"* {summary}")
            else:
                ui.text_disabled(summary)

            ui.same_line()
            if ui.small_button(f"{'Close' if is_open else 'Edit'}##{nid}"):
                self._toggle_editor(node)

            if ed and not is_open:
                ui.same_line()
                if ui.small_button(f"X##{nid}"):
                    self._edits.pop(nid, None)
                    self._status = f"{node.name} draft discarded."

            if is_open:
                self._draw_inline_editor(ui, node, kf_nodes)
