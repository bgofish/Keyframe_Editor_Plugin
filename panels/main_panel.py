"""
Keyframe Editor Panel - FINAL VERSION v5
- Fixed time multiplier => +/- buttonsremoved & changed to 3 decimal places
- Duplicate, Copy/Paste, Reorder (↑↓), Delete keyframe
- Global time multiplier toolbar with presets and custom value
- Easing selector (no easing on last frame)
- All 9 fields editable via JSON round-trip
- Layout: Label | [value box] | [slider] | [-] Med [+]
"""
from __future__ import annotations
import copy
import json
import tempfile
import os
import lichtfeld as lf

import sys
_plugin_dir = os.path.dirname(os.path.abspath(__file__))
if _plugin_dir not in sys.path:
    sys.path.insert(0, _plugin_dir)
_PP_IMPORT_ERR = ""
try:
    from lfs_path_player import LFSPathPlayer
    _HAS_PATH_PLAYER = True
except Exception as _e:
    _HAS_PATH_PLAYER = False
    _PP_IMPORT_ERR = str(_e)

_FLOAT_COLS = ["time", "pos_x", "pos_y", "pos_z", "rot_x", "rot_y", "rot_z", "rot_w", "lens"]
_EDIT_COLS  = _FLOAT_COLS

_SPEED_PRESETS = {
    "time":  [10.0, 1.0,  0.1],
    "lens":  [10.0, 1.0,  0.1],
    "pos_x": [1.0,  0.1,  0.001],
    "pos_y": [1.0,  0.1,  0.001],
    "pos_z": [1.0,  0.1,  0.001],
    "rot_x": [0.01, 0.001, 0.0001],
    "rot_y": [0.01, 0.001, 0.0001],
    "rot_z": [0.01, 0.001, 0.0001],
    "rot_w": [0.01, 0.001, 0.0001],
}
_SPEED_LABELS  = ["Fast", "Med", "Fine"]
_EASING_LABELS = ["Linear", "EaseIn", "EaseOut", "EaseInOut"]
_TIME_MULTIPLIERS = [0.02, 0.05, 0.1, 0.2, 0.5, 2.0, 5.0, 10.0, 20.0, 50.0]

_SUMMARY_W = 440
_DRAG_W    = 200
_VAL_W     = 100

# (col, label, min, max)
_EDITOR_FIELDS = [
    ("time",  "Time",   0.0,    3600.0),
    ("lens",  "Lens",   1.0,    300.0),
    ("pos_x", "Pos X",  -200.0, 200.0),
    ("pos_y", "Pos Y",  -200.0, 200.0),
    ("pos_z", "Pos Z",  -200.0, 200.0),
    ("rot_x", "Rot X",  -1.0,   1.0),
    ("rot_y", "Rot Y",  -1.0,   1.0),
    ("rot_z", "Rot Z",  -1.0,   1.0),
    ("rot_w", "Rot W",  -1.0,   1.0),
]

_GROUP_BEFORE = {
    "time":  "Time & Lens",
    "pos_x": "Position",
    "rot_x": "Rotation (quaternion)",
}


# ── JSON helpers ──────────────────────────────────────────────────────────────

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
        "time":   float(kf.time),
        "pos_x":  float(pos[0]), "pos_y": float(pos[1]), "pos_z": float(pos[2]),
        "rot_x":  float(rot[0]), "rot_y": float(rot[1]),
        "rot_z":  float(rot[2]), "rot_w": float(rot[3]),
        "lens":   float(kf.focal_length_mm),
        "easing": int(kf.easing),
    }


def _load_camera_path_json() -> dict | None:
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


def _reload_from_keyframe_list(keyframe_list: list, version: int = 3) -> str:
    try:
        data = {"version": version, "keyframes": keyframe_list}
        tmp  = tempfile.mktemp(suffix=".json")
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        lf.ui.load_camera_path(tmp)
        try:
            os.remove(tmp)
        except Exception:
            pass
        return ""
    except Exception as exc:
        return str(exc)


def _write_all_keyframes(all_nodes: list, edits: dict) -> str:
    try:
        data = _load_camera_path_json()
        if data is None:
            return "Failed to save camera path"

        keyframes    = data.get("keyframes", [])
        nodes_sorted = sorted(all_nodes, key=lambda n: float(n.keyframe_data().time))

        if len(nodes_sorted) != len(keyframes):
            return (f"Node count mismatch: {len(nodes_sorted)} nodes "
                    f"vs {len(keyframes)} JSON entries")

        for i, node in enumerate(nodes_sorted):
            nid = str(node.id)
            if nid not in edits:
                continue
            ed = edits[nid]
            kf = keyframes[i]

            if "time" in ed: kf["time"]            = float(ed["time"])
            if "lens" in ed: kf["focal_length_mm"] = float(ed["lens"])
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
            if "easing" in ed and i < len(keyframes) - 1:
                kf["easing"] = int(ed["easing"])

        return _reload_from_keyframe_list(keyframes, data.get("version", 3))

    except Exception as exc:
        print(f"[KFEditor] _write_all_keyframes error: {exc}")
        return str(exc)


def _write_single_node(node, d: dict, all_nodes: list) -> str:
    return _write_all_keyframes(all_nodes, {str(node.id): d})


def _fmt(v: float) -> str:
    return f"{v:.3f}"


def _try_input_float(ui, uid, val, width):
    ui.set_next_item_width(width)
    changed, new_val = ui.input_float(uid, val)
    return changed, float(new_val)


# ── Panel ─────────────────────────────────────────────────────────────────────

class KeyframeEditorPanel(lf.ui.Panel):
    id    = "keyframe_editor.panel"
    label = "Keyframe Editor"
    space = lf.ui.PanelSpace.MAIN_PANEL_TAB
    order = 200
    #template = ""
    #style    = ""
    #height_mode       = lf.ui.PanelHeightMode.FILL
    ##poll_dependencies = {lf.ui.PollDependency.SCENE}
    #poll_dependencies = [lf.ui.PollDependency.SCENE]
    @classmethod
    def poll(cls, context) -> bool:
        return True

    def __init__(self):
        self._edits:         dict[str, dict] = {}
        self._expanded:      str | None = None
        self._edit_buf:      dict = {}
        self._speed_idx:     dict[str, dict[str, int]] = {}
        self._clipboard:     dict | None = None
        self._time_mult:     float = 1.000
        self._time_mult_str: str = "1.001"
        self._status:        str = ""

        # ── Path Player state ─────────────────────────────────────────────
        self._pp_player        = None
        self._pp_path          = ""
        self._pp_speed         = 1.0
        self._pp_loop          = True
        self._pp_playing       = False
        self._pp_elapsed       = 0.0
        self._pp_last_tick     = 0.0
        self._pp_start_wall    = 0.0
        self._pp_start_elapsed = 0.0
        self._pp_show          = False
        self._pp_status        = ""
    # ── helpers ───────────────────────────────────────────────────────────

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

    def _set_time_mult(self, value: float):
        self._time_mult     = max(0.01, round(value, 3))
        self._time_mult_str = f"{self._time_mult:.3f}"

    # ── global operations ─────────────────────────────────────────────────

    def _apply_time_multiplier(self, multiplier: float, all_nodes: list) -> str:
        try:
            data = _load_camera_path_json()
            if data is None:
                return "Failed to load camera path"
            for kf in data.get("keyframes", []):
                kf["time"] = float(kf["time"]) * multiplier
            return _reload_from_keyframe_list(
                data["keyframes"], data.get("version", 3)
            )
        except Exception as exc:
            return str(exc)

    def _duplicate_keyframe(self, node, all_nodes: list) -> str:
        try:
            data = _load_camera_path_json()
            if data is None:
                return "Failed to load camera path"

            keyframes    = data.get("keyframes", [])
            nodes_sorted = sorted(all_nodes, key=lambda n: float(n.keyframe_data().time))

            if len(nodes_sorted) != len(keyframes):
                return "Node count mismatch"

            idx = next((i for i, n in enumerate(nodes_sorted)
                        if str(n.id) == str(node.id)), None)
            if idx is None:
                return "Node not found"

            new_kf         = copy.deepcopy(keyframes[idx])
            new_kf["time"] = float(new_kf["time"]) + 1.0
            keyframes.insert(idx + 1, new_kf)
            return _reload_from_keyframe_list(keyframes, data.get("version", 3))
        except Exception as exc:
            return str(exc)

    def _delete_keyframe(self, node, all_nodes: list) -> str:
        try:
            data = _load_camera_path_json()
            if data is None:
                return "Failed to load camera path"

            keyframes    = data.get("keyframes", [])
            nodes_sorted = sorted(all_nodes, key=lambda n: float(n.keyframe_data().time))

            if len(nodes_sorted) != len(keyframes):
                return "Node count mismatch"

            if len(keyframes) <= 1:
                return "Cannot delete the only keyframe."

            idx = next((i for i, n in enumerate(nodes_sorted)
                        if str(n.id) == str(node.id)), None)
            if idx is None:
                return "Node not found"

            keyframes.pop(idx)
            return _reload_from_keyframe_list(keyframes, data.get("version", 3))
        except Exception as exc:
            return str(exc)

    def _move_keyframe(self, node, direction: int, all_nodes: list) -> str:
        try:
            data = _load_camera_path_json()
            if data is None:
                return "Failed to load camera path"

            keyframes    = data.get("keyframes", [])
            nodes_sorted = sorted(all_nodes, key=lambda n: float(n.keyframe_data().time))

            if len(nodes_sorted) != len(keyframes):
                return "Node count mismatch"

            idx = next((i for i, n in enumerate(nodes_sorted)
                        if str(n.id) == str(node.id)), None)
            if idx is None:
                return "Node not found"

            swap_idx = idx + direction
            if swap_idx < 0 or swap_idx >= len(keyframes):
                return ""

            t_a = keyframes[idx]["time"]
            t_b = keyframes[swap_idx]["time"]
            keyframes[idx]["time"]      = t_b
            keyframes[swap_idx]["time"] = t_a
            keyframes.sort(key=lambda k: k["time"])
            return _reload_from_keyframe_list(keyframes, data.get("version", 3))
        except Exception as exc:
            return str(exc)

    # ── inline editor ─────────────────────────────────────────────────────

    def _draw_inline_editor(self, ui, node, kf_nodes, is_last: bool):
        nid  = str(node.id)
        live = _node_to_dict(node)

        for k in _FLOAT_COLS:
            if k not in self._edit_buf:
                self._edit_buf[k] = live[k]
        if "easing" not in self._edit_buf:
            self._edit_buf["easing"] = live["easing"]
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

            ui.label(lbl)
            ui.same_line()

            val_changed, typed_val = _try_input_float(
                ui, f"##val_{nid}_{col}", buf[col], _VAL_W
            )
            if val_changed:
                buf[col] = max(mn, min(mx, typed_val))
            ui.same_line()

            ui.set_next_item_width(_DRAG_W)
            try:
                changed, new_val = ui.slider_float(
                    f"##drag_{nid}_{col}", buf[col], mn, mx
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

            if ui.small_button(f"-##{nid}_{col}"):
                self._cycle_speed(nid, col, -1)
            ui.same_line()
            ui.label(spd_lbl)
            ui.same_line()
            if ui.small_button(f"+##{nid}_{col}"):
                self._cycle_speed(nid, col, +1)

        # ── Easing ────────────────────────────────────────────────────────
        ui.spacing()
        ui.label("Easing")
        ui.separator()

        if is_last:
            ui.text_disabled("No easing on last keyframe.")
        else:
            cur_easing = int(buf.get("easing", 0))
            for i, elbl in enumerate(_EASING_LABELS):
                if cur_easing == i:
                    ui.button_styled(f"{elbl}##{nid}_e{i}", "primary")
                else:
                    if ui.button(f"{elbl}##{nid}_e{i}"):
                        buf["easing"] = i
                if i < len(_EASING_LABELS) - 1:
                    ui.same_line()

        ui.spacing()
        ui.separator()
        ui.spacing()

        # ── Action buttons ─────────────────────────────────────────────────
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

        if ui.button(f"Save Draft##{nid}"):
            live2 = _node_to_dict(node)
            draft = {k: buf[k] for k in _FLOAT_COLS if buf[k] != live2[k]}
            if not is_last and int(buf.get("easing", 0)) != int(live2.get("easing", 0)):
                draft["easing"] = int(buf["easing"])
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

    # ── Path Player section ───────────────────────────────────────────────

    _PP_HANDLER = "kf_editor_path_preview"

    def _pp_start(self):
        """Register the draw handler that drives real-time camera playback."""
        import time as _time
        self._pp_playing   = True
        self._pp_start_wall = _time.time()
        self._pp_start_elapsed = self._pp_elapsed
        try:
            lf.remove_draw_handler(self._PP_HANDLER)
        except Exception:
            pass
        lf.add_draw_handler(self._PP_HANDLER, self._pp_draw_handler, "POST_VIEW")
        lf.ui.request_redraw()

    def _pp_stop(self, reset: bool = False):
        """Unregister the draw handler and optionally reset playhead."""
        self._pp_playing = False
        try:
            lf.remove_draw_handler(self._PP_HANDLER)
        except Exception:
            pass
        if reset:
            self._pp_elapsed = 0.0
        lf.ui.request_redraw()

    def _pp_draw_handler(self, ctx) -> None:
        """POST_VIEW draw handler — advances clock and moves the viewport camera."""
        import time as _time
        if not self._pp_playing or self._pp_player is None:
            self._pp_stop()
            return

        elapsed = ((_time.time() - self._pp_start_wall) * self._pp_speed
                   + self._pp_start_elapsed)
        dur = self._pp_player.total_duration

        if self._pp_loop:
            elapsed = elapsed % dur
        elif elapsed >= dur:
            elapsed = dur
            self._pp_stop()
            self._pp_elapsed = dur
            self._pp_status  = "Playback complete."
            return

        self._pp_elapsed = elapsed

        try:
            eye, target, up, fov = self._pp_player.get_camera_at_snap(
                0, 1.0, self._pp_loop  # unused snap_index — we pass t directly below
            )
            # Call _interpolate directly so we drive by real time, not snap index
            pos, rot, pfov = self._pp_player._interpolate(elapsed, loop=self._pp_loop)
            import math as _math
            from lfs_path_player import _quat_rotate
            forward = _quat_rotate(rot, (0.0, 0.0, 1.0))
            up_vec  = _quat_rotate(rot, (0.0, 1.0, 0.0))
            target  = (pos[0] + forward[0], pos[1] + forward[1], pos[2] + forward[2])
            lf.set_camera(pos, target, up_vec)
            lf.set_camera_fov(pfov)
        except Exception as exc:
            self._pp_stop()
            self._pp_status = f"Camera error: {exc}"
            return

        lf.ui.request_redraw()

    def _draw_path_player(self, ui):
        """Collapsible real-time path playback section powered by LFSPathPlayer."""
        ui.spacing()
        toggle_lbl = "▼ Path Player" if self._pp_show else "▶ Path Player"
        if ui.button(toggle_lbl):
            self._pp_show = not self._pp_show
        ui.separator()

        if not self._pp_show:
            return

        if not _HAS_PATH_PLAYER:
            ui.text_disabled(f"lfs_path_player import failed: {_PP_IMPORT_ERR}")
            ui.text_disabled(f"Plugin dir on sys.path: {_plugin_dir}")
            return

        # ── Load ──────────────────────────────────────────────────────
        if ui.button("Load Path##pp_load"):
            self._pp_stop(reset=True)
            try:
                tmp = tempfile.mktemp(suffix=".json")
                lf.ui.save_camera_path(tmp)
                self._pp_player = LFSPathPlayer(tmp)
                self._pp_status = (f"Loaded  —  {self._pp_player.n_keyframes} keyframes  |  "
                                   f"duration {self._pp_player.total_duration:.2f}s")
            except Exception as exc:
                self._pp_player = None
                self._pp_status = f"Load error: {exc}"

        if self._pp_status:
            ui.label(self._pp_status)

        if self._pp_player is None:
            ui.text_disabled("No path loaded.")
            return

        dur = self._pp_player.total_duration
        ui.separator()

        # ── Speed & Loop ──────────────────────────────────────────────
        ui.label("Speed:")
        ui.same_line()
        spd_changed, new_spd = _try_input_float(ui, "##pp_spd", self._pp_speed, 60)
        if spd_changed and new_spd > 0.0:
            self._pp_speed = new_spd
        ui.same_line()
        ui.label("x    Loop(leave ON to stop crashing) :")
        ui.same_line()
        lp_changed, new_lp = ui.checkbox("##pp_loop", self._pp_loop)
        if lp_changed:
            self._pp_loop = bool(new_lp)

        # ── Transport ─────────────────────────────────────────────────
        ui.spacing()
        play_lbl = "⏸ Pause##pp_play" if self._pp_playing else "▶ Play##pp_play"
        if ui.button_styled(play_lbl, "primary"):
            if not self._pp_playing:
                if self._pp_elapsed >= dur and not self._pp_loop:
                    self._pp_elapsed = 0.0
                self._pp_status = "Playing…"
                self._pp_start()
            else:
                self._pp_stop()
                self._pp_status = f"Paused at {self._pp_elapsed:.2f}s"

        ui.same_line()
        if ui.button("⏹ Stop##pp_stop"):
            self._pp_stop(reset=True)
            self._pp_status = "Stopped."

        # ── Scrub slider (only when paused) ───────────────────────────
        ui.spacing()
        ui.label(f"Time: {self._pp_elapsed:.2f}s / {dur:.2f}s")
        ui.set_next_item_width(350)
        scrub_changed, scrub_val = ui.slider_float(
            "##pp_scrub", self._pp_elapsed, 0.0, dur
        )
        if scrub_changed and not self._pp_playing:
            self._pp_elapsed = float(scrub_val)
            try:
                pos, rot, pfov = self._pp_player._interpolate(self._pp_elapsed, loop=self._pp_loop)
                import math as _math
                from lfs_path_player import _quat_rotate
                forward = _quat_rotate(rot, (0.0, 0.0, 1.0))
                up_vec  = _quat_rotate(rot, (0.0, 1.0, 0.0))
                target  = (pos[0] + forward[0], pos[1] + forward[1], pos[2] + forward[2])
                lf.set_camera(pos, target, up_vec)
                lf.set_camera_fov(pfov)
            except Exception as exc:
                self._pp_status = f"Scrub error: {exc}"

        ui.spacing()
        ui.separator()

    # ── main draw ─────────────────────────────────────────────────────────

    def draw(self, ui):
        ui.heading("Keyframe Editor")

        kf_nodes = _get_kf_nodes()
        if not kf_nodes:
            ui.text_disabled("No keyframe nodes found in scene.")
            return

        kf_nodes_sorted = sorted(kf_nodes, key=lambda n: float(n.keyframe_data().time))
        last_nid        = str(kf_nodes_sorted[-1].id) if kf_nodes_sorted else None

        if self._status:
            ui.label(self._status)

        # ── Primary toolbar ───────────────────────────────────────────────
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

        # ── Time multiplier toolbar ───────────────────────────────────────
        ui.spacing()
        ui.label("Time Multiplier")
        ui.separator()

        # Preset buttons
        ui.label("Presets:")
        ui.same_line()
        for mult in _TIME_MULTIPLIERS:
            lbl = (f"{int(mult)}x" if mult >= 1.0 and mult == int(mult)
                   else f"{mult}x")
            if ui.small_button(f"{lbl}##tm"):
                e = self._apply_time_multiplier(mult, kf_nodes)
                self._status = f"Error: {e}" if e else f"All times × {lbl}."
            ui.same_line()
        ui.new_line()

        ui.label("Custom-x:")

        ui.same_line()
        val_changed, new_mult = _try_input_float(
            ui, "##custom_mult_manual", self._time_mult, 80
        )
        if val_changed:
            self._set_time_mult(new_mult)
        ui.same_line()
        if ui.button("Apply##cm"):
            e = self._apply_time_multiplier(self._time_mult, kf_nodes)
            self._status = f"Error: {e}" if e else f"All times × {self._time_mult:.3f}."

        ui.separator()

        pending = sum(len(v) for v in self._edits.values())
        ui.label(
            f"{len(kf_nodes)} keyframe(s)" +
            (f"  |  {pending} unsaved change(s)" if pending else "") +
            (f"  |  clipboard: t={_fmt(self._clipboard['time'])}"
             if self._clipboard else "")
        )
        ui.separator()

        # ── Column header ─────────────────────────────────────────────────
        ui.label("Name")
        ui.same_line()
        ui.set_next_item_width(_SUMMARY_W)
        ui.label("Summary  (Time | Pos | Rot | Lens | Easing)")
        ui.same_line()
        ui.label("Actions")
        ui.separator()

        # ── Data rows ─────────────────────────────────────────────────────
        for node in kf_nodes_sorted:
            nid      = str(node.id)
            live     = _node_to_dict(node)
            ed       = self._edits.get(nid, {})
            cur      = {**live, **ed}
            is_open  = (self._expanded == nid)
            is_last  = (nid == last_nid)
            is_first = (node is kf_nodes_sorted[0])

            ui.label(node.name)
            ui.same_line()

            easing_str = ("" if is_last
                          else f"  e={_EASING_LABELS[int(cur.get('easing', 0))]}")
            summary = (
                f"t={_fmt(cur['time'])}  "
                f"p=({_fmt(cur['pos_x'])}, {_fmt(cur['pos_y'])}, {_fmt(cur['pos_z'])})  "
                f"r=({_fmt(cur['rot_x'])}, {_fmt(cur['rot_y'])}, "
                f"{_fmt(cur['rot_z'])}, {_fmt(cur['rot_w'])})  "
                f"l={_fmt(cur['lens'])}"
                f"{easing_str}"
            )
            ui.set_next_item_width(_SUMMARY_W)
            if ed:
                ui.label(f"* {summary}")
            else:
                ui.text_disabled(summary)

            ui.same_line()

            # Edit / Close
            if ui.small_button(f"{'Close' if is_open else 'Edit'}##{nid}"):
                self._toggle_editor(node)
            ui.same_line()

            # Copy
            if ui.small_button(f"Copy##{nid}"):
                self._clipboard = copy.deepcopy(cur)
                self._status    = f"Copied {node.name}."
            ui.same_line()

            # Paste
            if self._clipboard is not None:
                if ui.small_button(f"Paste##{nid}"):
                    paste           = copy.deepcopy(self._clipboard)
                    paste["time"]   = live["time"]
                    paste["easing"] = live["easing"]
                    e = _write_single_node(node, paste, kf_nodes)
                    self._status = f"Error: {e}" if e else f"Pasted into {node.name}."
                ui.same_line()

            # Duplicate
            if ui.small_button(f"Dup##{nid}"):
                e = self._duplicate_keyframe(node, kf_nodes)
                self._status = f"Error: {e}" if e else f"Duplicated {node.name}."
            ui.same_line()

            # Move Up
            if not is_first:
                if ui.small_button(f"↑##{nid}"):
                    e = self._move_keyframe(node, -1, kf_nodes)
                    self._status = f"Error: {e}" if e else f"{node.name} moved earlier."
                ui.same_line()

            # Move Down
            if not is_last:
                if ui.small_button(f"↓##{nid}"):
                    e = self._move_keyframe(node, +1, kf_nodes)
                    self._status = f"Error: {e}" if e else f"{node.name} moved later."
                ui.same_line()

            # Delete
            if ui.small_button(f"Del##{nid}"):
                e = self._delete_keyframe(node, kf_nodes)
                if e:
                    self._status = f"Error: {e}"
                else:
                    self._edits.pop(nid, None)
                    if self._expanded == nid:
                        self._expanded = None
                        self._edit_buf = {}
                    self._status = f"{node.name} deleted."

            # Discard draft
            if ed and not is_open:
                ui.same_line()
                if ui.small_button(f"X##{nid}"):
                    self._edits.pop(nid, None)
                    self._status = f"{node.name} draft discarded."

            if is_open:
                self._draw_inline_editor(ui, node, kf_nodes, is_last)

        # ── Path Player ───────────────────────────────────────────────────
        self._draw_path_player(ui)
