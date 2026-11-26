"""Put app windows she opens on the monitor you chose (COSMIC).

On Wayland an app can't pick its monitor: COSMIC opens a new window where you last were,
which is wherever she is when you click her buttons. COSMIC's toplevel manager can move a
window to another monitor's workspace, so this follows the monitors, their active
workspaces (ext-workspace) and the windows (ext-foreign-toplevel-list, with COSMIC's
toplevel info for the monitor each one is on) on its own Wayland connection, in a
thread, and moves a window you asked for once it shows up.

The COSMIC protocol bindings are in protocols/ (generated from protocols-xml/).
"""

import select
import sys
import threading
import time

from pywayland.client import Display
from pywayland.protocol.ext_foreign_toplevel_list_v1 import ExtForeignToplevelListV1
from pywayland.protocol.ext_workspace_v1 import ExtWorkspaceManagerV1
from pywayland.protocol.wayland import WlOutput

from kawaii.wayland.protocols.cosmic_toplevel_info_unstable_v1 import ZcosmicToplevelInfoV1
from kawaii.wayland.protocols.cosmic_toplevel_management_unstable_v1 import ZcosmicToplevelManagerV1

ACTIVE = 1  # ext_workspace_handle_v1 state bit


class WindowMover:
    def __init__(self):
        self.available = False  # the compositor lets us move windows (COSMIC)
        self.monitors = []  # [(name, width, height, model)], biggest first, for the setting
        self._outputs = {}  # wl_output -> {"name", "w", "h", "model"}
        self._groups = {}  # workspace group -> {"outputs": set, "workspaces": list}
        self._workspaces = {}  # workspace -> {"active": bool}
        self._windows = {}  # foreign toplevel -> {"app", "title", "outputs", "cosmic", "seen"}
        self._wanted = []  # moves asked for, not done yet
        self._lock = threading.Lock()
        threading.Thread(target=self._run, daemon=True, name="winmove").start()

    def largest(self):
        """Name of the monitor with the most pixels, or None."""
        return max(self.monitors, key=lambda m: m[1] * m[2])[0] if self.monitors else None

    def expect(self, output, app=None, title=None, seconds=25, lookback=0.5):
        """Move the next window that opens (of `app`, an app id like 'kiro', when given) to the
        monitor named `output`; a window already open whose title contains `title` counts too
        (an app that reuses its window), and so does one that opened up to `lookback` seconds
        ago (for when we only hear about the launch afterwards). Forgotten after `seconds`."""
        if not output:
            return
        with self._lock:
            self._wanted.append({"output": output, "app": app.lower() if app else None, "title": title,
                                 "since": time.monotonic() - lookback, "until": time.monotonic() + seconds,
                                 "window": None, "next_try": 0.0})

    # ---- the connection --------------------------------------------------------

    def _run(self):
        try:
            self._connect()
        except Exception as e:  # not COSMIC, or no Wayland: the setting just has nothing to do
            print(f"winmove: cannot move windows here ({e})", file=sys.stderr)
            return
        fd = self.display.get_fd()
        while True:
            self.display.flush()
            readable, _, _ = select.select([fd], [], [], 0.25)
            if readable:
                self.display.dispatch(block=True)  # data is waiting: this reads it, it doesn't block
            self._move_due()

    def _connect(self):
        self.display = Display()
        self.display.connect()
        registry = self.display.get_registry()
        found = {}
        registry.dispatcher["global"] = lambda _, name, iface, version: found.setdefault(iface, []).append(
            (name, version))
        self.display.roundtrip()
        for iface in ("zcosmic_toplevel_manager_v1", "zcosmic_toplevel_info_v1", "ext_foreign_toplevel_list_v1",
                      "ext_workspace_manager_v1"):
            if iface not in found:
                raise RuntimeError(f"no {iface}")
        for name, version in found.get("wl_output", []):
            self._add_output(registry.bind(name, WlOutput, min(version, 4)))
        self.manager = registry.bind(found["zcosmic_toplevel_manager_v1"][0][0], ZcosmicToplevelManagerV1, 4)
        self.info = registry.bind(found["zcosmic_toplevel_info_v1"][0][0], ZcosmicToplevelInfoV1, 3)
        self.toplevels = registry.bind(found["ext_foreign_toplevel_list_v1"][0][0], ExtForeignToplevelListV1, 1)
        self.toplevels.dispatcher["toplevel"] = self._add_window
        self.workspace_manager = registry.bind(found["ext_workspace_manager_v1"][0][0], ExtWorkspaceManagerV1, 1)
        self.workspace_manager.dispatcher["workspace_group"] = self._add_group
        self.workspace_manager.dispatcher["workspace"] = self._add_workspace
        self.display.roundtrip()
        self.available = True

    def _add_output(self, proxy):
        o = self._outputs[proxy] = {"name": None, "w": 0, "h": 0, "model": ""}

        def name(_, n):
            o["name"] = n
            self._list_monitors()

        def mode(_, flags, w, h, refresh):
            if flags & 1:  # the current mode
                o["w"], o["h"] = w, h
                self._list_monitors()
        proxy.dispatcher["name"] = name
        proxy.dispatcher["mode"] = mode
        proxy.dispatcher["geometry"] = lambda _, x, y, pw, ph, subpixel, make, model, transform: o.update(model=model)

    def _list_monitors(self):
        self.monitors = sorted(((o["name"], o["w"], o["h"], o["model"]) for o in self._outputs.values() if o["name"]),
                               key=lambda m: -m[1] * m[2])

    def _add_group(self, _, group):
        g = self._groups[group] = {"outputs": set(), "workspaces": []}
        group.dispatcher["output_enter"] = lambda _, o: g["outputs"].add(o)
        group.dispatcher["output_leave"] = lambda _, o: g["outputs"].discard(o)
        group.dispatcher["workspace_enter"] = lambda _, w: g["workspaces"].append(w)
        group.dispatcher["workspace_leave"] = lambda _, w: w in g["workspaces"] and g["workspaces"].remove(w)
        group.dispatcher["removed"] = lambda _: self._groups.pop(group, None)

    def _add_workspace(self, _, workspace):
        w = self._workspaces[workspace] = {"active": False}
        workspace.dispatcher["state"] = lambda _, state: w.update(active=bool(state & ACTIVE))
        workspace.dispatcher["removed"] = lambda _: self._workspaces.pop(workspace, None)

    def _add_window(self, _, handle):
        # The COSMIC handle tells which monitor it is on (that arrives a moment later).
        win = self._windows[handle] = {"app": "", "title": "", "outputs": set(), "seen": time.monotonic(),
                                       "cosmic": self.info.get_cosmic_toplevel(handle)}
        handle.dispatcher["app_id"] = lambda _, a: win.update(app=a)
        handle.dispatcher["title"] = lambda _, t: win.update(title=t)
        handle.dispatcher["closed"] = lambda _: self._windows.pop(handle, None)
        win["cosmic"].dispatcher["output_enter"] = lambda _, o: win["outputs"].add(o)
        win["cosmic"].dispatcher["output_leave"] = lambda _, o: win["outputs"].discard(o)

    # ---- moving ------------------------------------------------------------------

    def _move_due(self):
        now = time.monotonic()
        with self._lock:
            self._wanted = [w for w in self._wanted if now < w["until"]]
            wanted = list(self._wanted)
        for want in wanted:
            target = next((p for p, o in self._outputs.items() if o["name"] == want["output"]), None)
            if target is None:
                continue
            win = want["window"]
            if win is None or win not in self._windows.values():  # pick the window once it is there
                windows = [w for w in self._windows.values() if not want["app"] or want["app"] in w["app"].lower()]
                fresh = [w for w in windows if w["seen"] >= want["since"]]
                fresh += [w for w in windows if want["title"] and want["title"] in w["title"] and w not in fresh]
                win = want["window"] = max(fresh, key=lambda w: w["seen"], default=None)
            if win is None or not win["outputs"]:  # not open yet, or COSMIC hasn't said where it is
                continue
            if target in win["outputs"]:  # there (it opened there, or the move worked): done
                with self._lock:
                    if want in self._wanted:
                        self._wanted.remove(want)
                continue
            # A window that has only just appeared can ignore a move, so ask again until it is there.
            workspace = self._active_workspace(target)
            if workspace is not None and now >= want["next_try"]:
                self.manager.move_to_ext_workspace(win["cosmic"], workspace, target)
                want["next_try"] = now + 1.0

    def _active_workspace(self, output):
        for g in self._groups.values():
            if output in g["outputs"]:
                return next((w for w in g["workspaces"] if self._workspaces.get(w, {}).get("active")),
                            g["workspaces"][0] if g["workspaces"] else None)
        return None
