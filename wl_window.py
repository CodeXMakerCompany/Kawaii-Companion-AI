"""Native Wayland overlay window: a wlr-layer-shell surface with an EGL/OpenGL context.

Layer surfaces are what panels and docks use, so the compositor treats them as
part of the desktop: no focus outline, no tiling or maximizing, always above
normal windows, and an input region lets clicks on transparent pixels fall
through to whatever is underneath.

Requires PYOPENGL_PLATFORM=egl to be set before OpenGL is imported.
"""

import ctypes
import mmap
import os
import select
import sys
import time

from OpenGL import EGL
from pywayland._ffi import ffi
from pywayland.client import Display
from pywayland.protocol.cursor_shape_v1 import WpCursorShapeDeviceV1, WpCursorShapeManagerV1
from pywayland.protocol.wayland import WlCompositor, WlOutput, WlSeat
from pywayland.protocol.xdg_output_unstable_v1 import ZxdgOutputManagerV1

from protocols.wlr_layer_shell_unstable_v1 import ZwlrLayerShellV1, ZwlrLayerSurfaceV1

BTN_LEFT, BTN_RIGHT = 0x110, 0x111

_wl_egl = ctypes.CDLL("libwayland-egl.so.1")
_wl_egl.wl_egl_window_create.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
_wl_egl.wl_egl_window_create.restype = ctypes.c_void_p
_wl_egl.wl_egl_window_resize.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
_wl_egl.wl_egl_window_destroy.argtypes = [ctypes.c_void_p]

# The read/prepare/cancel trio (pywayland lacks cancel_read). Needed because Mesa's EGL
# reads the same socket: a plain blocking dispatch after select() can find the data
# already taken and then sleep forever.
_wl = ctypes.CDLL("libwayland-client.so.0")
for _fn in ("wl_display_prepare_read", "wl_display_read_events", "wl_display_cancel_read",
            "wl_display_dispatch_pending", "wl_display_flush"):
    getattr(_wl, _fn).argtypes = [ctypes.c_void_p]


def _quiet_stale_events(hook=sys.unraisablehook):
    """Hopping monitors destroys our old surface; the compositor may still send a pointer
    'leave' naming it, which pywayland reports as an ignored exception. Drop just that one."""

    def filtered(info):
        if not (isinstance(info.exc_value, RuntimeError) and "may already be destroyed" in str(info.exc_value)):
            hook(info)

    sys.unraisablehook = filtered


_quiet_stale_events()


def _addr(proxy):
    return int(ffi.cast("uintptr_t", proxy._ptr))


class Xkb:
    """Keymap, modifier state and compose (dead keys) through libxkbcommon."""

    def __init__(self):
        x = self.x = ctypes.CDLL("libxkbcommon.so.0")
        vp, u32 = ctypes.c_void_p, ctypes.c_uint32
        x.xkb_context_new.restype = vp
        x.xkb_keymap_new_from_string.argtypes = [vp, ctypes.c_char_p, ctypes.c_int, ctypes.c_int]
        x.xkb_keymap_new_from_string.restype = vp
        x.xkb_keymap_unref.argtypes = [vp]
        x.xkb_keymap_key_repeats.argtypes = [vp, u32]
        x.xkb_state_new.argtypes = [vp]
        x.xkb_state_new.restype = vp
        x.xkb_state_unref.argtypes = [vp]
        x.xkb_state_update_mask.argtypes = [vp, u32, u32, u32, u32, u32, u32]
        x.xkb_state_key_get_one_sym.argtypes = [vp, u32]
        x.xkb_state_key_get_one_sym.restype = u32
        x.xkb_state_key_get_utf8.argtypes = [vp, u32, ctypes.c_char_p, ctypes.c_size_t]
        x.xkb_state_mod_name_is_active.argtypes = [vp, ctypes.c_char_p, ctypes.c_int]
        x.xkb_compose_table_new_from_locale.argtypes = [vp, ctypes.c_char_p, ctypes.c_int]
        x.xkb_compose_table_new_from_locale.restype = vp
        x.xkb_compose_state_new.argtypes = [vp, ctypes.c_int]
        x.xkb_compose_state_new.restype = vp
        x.xkb_compose_state_feed.argtypes = [vp, u32]
        x.xkb_compose_state_get_status.argtypes = [vp]
        x.xkb_compose_state_get_utf8.argtypes = [vp, ctypes.c_char_p, ctypes.c_size_t]
        x.xkb_compose_state_reset.argtypes = [vp]

        self.ctx = x.xkb_context_new(0)
        self.keymap = self.state = None
        locale = os.environ.get("LC_ALL") or os.environ.get("LC_CTYPE") or os.environ.get("LANG") or "C"
        table = x.xkb_compose_table_new_from_locale(self.ctx, locale.encode(), 0)
        self.compose = x.xkb_compose_state_new(table, 0) if table else None

    def set_keymap(self, text):
        keymap = self.x.xkb_keymap_new_from_string(self.ctx, text, 1, 0)
        if not keymap:
            return
        if self.state:
            self.x.xkb_state_unref(self.state)
            self.x.xkb_keymap_unref(self.keymap)
        self.keymap, self.state = keymap, self.x.xkb_state_new(keymap)

    def update_mods(self, depressed, latched, locked, group):
        if self.state:
            self.x.xkb_state_update_mask(self.state, depressed, latched, locked, 0, 0, group)

    def ctrl(self):
        return bool(self.state and self.x.xkb_state_mod_name_is_active(self.state, b"Control", 8) > 0)

    def alt(self):
        return bool(self.state and self.x.xkb_state_mod_name_is_active(self.state, b"Mod1", 8) > 0)

    def repeats(self, key):
        return bool(self.keymap and self.x.xkb_keymap_key_repeats(self.keymap, key + 8))

    def text(self, key):
        """Text produced by a key press, honouring dead keys; '' if none."""
        if not self.state:
            return ""
        code = key + 8
        buf = ctypes.create_string_buffer(64)
        if self.compose:
            sym = self.x.xkb_state_key_get_one_sym(self.state, code)
            self.x.xkb_compose_state_feed(self.compose, sym)
            status = self.x.xkb_compose_state_get_status(self.compose)
            if status == 1:  # composing: wait for the next key
                return ""
            if status == 2:  # composed
                self.x.xkb_compose_state_get_utf8(self.compose, buf, 64)
                self.x.xkb_compose_state_reset(self.compose)
                return buf.value.decode("utf-8", "replace")
            if status == 3:  # cancelled
                self.x.xkb_compose_state_reset(self.compose)
                return ""
        self.x.xkb_state_key_get_utf8(self.state, code, buf, 64)
        return buf.value.decode("utf-8", "replace")


class Output:
    """A monitor in compositor (logical) coordinates."""

    def __init__(self, global_name, proxy):
        self.global_name = global_name
        self.proxy = proxy
        self.name = ""
        self.x = self.y = self.w = self.h = 0
        self.mode = (0, 0)  # fallback when xdg-output is missing
        self.scale = 1

    def contains(self, gx, gy):
        return self.x <= gx < self.x + self.w and self.y <= gy < self.y + self.h


class LayerWindow:
    """One overlay surface anchored top-left of a monitor; position is the (left, top) margin.

    A layer surface lives on exactly one monitor, so moving to another screen means
    recreating the surface there (the GL context, and with it every texture, survives).

    Callbacks (set as attributes): on_motion(x, y), on_leave(), on_button(button, pressed),
    on_scroll(steps), on_key(keycode, pressed), on_text(str), on_surface_changed().
    Keycodes are evdev codes.
    """

    def __init__(self, width, height, margin=(80, 80), output_name=None, namespace="shark-viewer"):
        self.width, self.height = width, height
        self.margin = list(margin)
        self.namespace = namespace
        self.closed = False  # app asked to quit
        self.lost = False  # compositor closed our surface (its monitor went away)
        self.on_motion = self.on_leave = self.on_button = self.on_scroll = self.on_key = self.on_text = None
        self.on_surface_changed = None

        self.display = Display()
        self.display.connect()
        self.globals = {}
        self.outputs = []
        self.output = None  # the monitor our surface is on
        output_globals = []
        self.registry = registry = self.display.get_registry()

        def on_global(reg, name, iface, ver):  # cffi callbacks must return None
            if iface == "wl_output":
                if hasattr(self, "compositor"):
                    self._add_output(name, ver)  # hot-plugged monitor
                else:
                    output_globals.append((name, ver))
            else:
                self.globals.setdefault(iface, (name, ver))

        def on_global_remove(reg, name):
            self.outputs = [o for o in self.outputs if o.global_name != name]

        registry.dispatcher["global"] = on_global
        registry.dispatcher["global_remove"] = on_global_remove
        self.display.roundtrip()
        if "zwlr_layer_shell_v1" not in self.globals:
            raise RuntimeError("this compositor has no wlr-layer-shell (COSMIC, KDE, Sway and Hyprland do)")

        def bind(interface, max_version):
            name, version = self.globals[interface.name]
            return registry.bind(name, interface, min(version, max_version))

        self.compositor = bind(WlCompositor, 4)
        self.layer_shell = bind(ZwlrLayerShellV1, 4)
        self.layer_version = min(self.globals["zwlr_layer_shell_v1"][1], 4)
        self.cursor_manager = bind(WpCursorShapeManagerV1, 1) if "wp_cursor_shape_manager_v1" in self.globals else None
        self.xdg_outputs = bind(ZxdgOutputManagerV1, 3) if "zxdg_output_manager_v1" in self.globals else None
        for name, ver in output_globals:
            self._add_output(name, ver)
        self.display.roundtrip()  # monitor positions and names

        self.xkb = Xkb()
        self.pointer = self.keyboard = self.cursor_device = None
        self.enter_serial = 0
        self.cursor_shape = None
        self.scroll_px = 0.0
        self.scroll_discrete = 0
        self.repeat_rate, self.repeat_delay = 25, 0.5
        self.held = None  # (key, next_repeat_time)
        if "wl_seat" in self.globals:
            self.seat = bind(WlSeat, 7)
            self.seat.dispatcher["capabilities"] = self._seat_caps

        self._init_egl()
        start = next((o for o in self.outputs if output_name and o.name == output_name), None)
        if start:
            self.margin = list(self._clamped(start, *self.margin))
        self._create_surface(start)

    # ---- monitors -----------------------------------------------------------
    def _add_output(self, name, version):
        o = Output(name, self.registry.bind(name, WlOutput, min(version, 4)))
        if self.xdg_outputs:
            xo = o.xdg = self.xdg_outputs.get_xdg_output(o.proxy)

            def position(_, x, y):
                o.x, o.y = x, y

            def size(_, w, h):
                o.w, o.h = w, h

            def set_name(_, n):
                o.name = n

            xo.dispatcher["logical_position"] = position
            xo.dispatcher["logical_size"] = size
            xo.dispatcher["name"] = set_name
        else:  # plain wl_output: position from geometry, logical size = current mode / scale

            def geometry(_, x, y, *rest):
                o.x, o.y = x, y

            def mode(_, flags, w, h, refresh):
                if flags & 1:
                    o.mode = (w, h)
                    o.w, o.h = w // o.scale, h // o.scale

            def scale(_, factor):
                o.scale = max(1, factor)
                o.w, o.h = o.mode[0] // o.scale, o.mode[1] // o.scale

            def set_name(_, n):
                o.name = n

            o.proxy.dispatcher["geometry"] = geometry
            o.proxy.dispatcher["mode"] = mode
            o.proxy.dispatcher["scale"] = scale
            o.proxy.dispatcher["name"] = set_name
        self.outputs.append(o)

    def output_at(self, gx, gy):
        return next((o for o in self.outputs if o.contains(gx, gy)), None)

    def _clamped(self, out, left, top):
        """Margins that keep the whole surface on `out` (just >= 0 if its size is unknown)."""
        left, top = max(0, int(left)), max(0, int(top))
        if out and out.w and out.h:
            left = min(left, max(0, out.w - self.width))
            top = min(top, max(0, out.h - self.height))
        return left, top

    def local_to_global(self, x, y):
        ox, oy = (self.output.x, self.output.y) if self.output else (0, 0)
        return ox + self.margin[0] + x, oy + self.margin[1] + y

    def place(self, tx, ty, gx, gy):
        """Put the top-left at global (tx, ty); hop to the monitor under the pointer (gx, gy)."""
        target = self.output_at(gx, gy)
        if target and self.output and target is not self.output:
            self.move_to_output(target, *self._clamped(target, tx - target.x, ty - target.y))
            return
        out = self.output
        left, top = (tx - out.x, ty - out.y) if out else (tx, ty)
        self.set_margin(*self._clamped(out, left, top))

    def move_to_output(self, output, left, top):
        if output and output.w and output.h:  # shrink to fit a smaller monitor
            self.width, self.height = min(self.width, output.w), min(self.height, output.h)
            left, top = self._clamped(output, left, top)
        self.margin = [left, top]
        self._destroy_surface()
        self._create_surface(output)
        if self.on_surface_changed:
            self.on_surface_changed()

    # ---- surface ------------------------------------------------------------
    def _create_surface(self, output):
        self.output = output
        self.configured = False
        self.surface = self.compositor.create_surface()
        self.surface.dispatcher["enter"] = self._surface_enter
        self.layer = self.layer_shell.get_layer_surface(
            self.surface, output.proxy if output else None, ZwlrLayerShellV1.layer.top, self.namespace)
        a = ZwlrLayerSurfaceV1.anchor
        self.layer.set_anchor(a.top | a.left)
        self.layer.set_exclusive_zone(-1)  # margins measured from the monitor edge, not the panel
        self.layer.set_size(self.width, self.height)
        self.layer.set_margin(self.margin[1], 0, 0, self.margin[0])
        ki = ZwlrLayerSurfaceV1.keyboard_interactivity
        # on_demand (v4): the compositor gives us the keyboard when clicked, like a normal window.
        self.layer.set_keyboard_interactivity(ki.on_demand if self.layer_version >= 4 else ki.exclusive)
        self.layer.dispatcher["configure"] = self._configure
        self.layer.dispatcher["closed"] = lambda *_: setattr(self, "lost", True)
        self.surface.commit()
        while not self.configured:
            self.display.dispatch(block=True)
        self.egl_window = _wl_egl.wl_egl_window_create(_addr(self.surface), self.width, self.height)
        self.egl_surface = EGL.eglCreateWindowSurface(self.egl_display, self.egl_config,
                                                      ctypes.cast(self.egl_window, EGL.EGLNativeWindowType), None)
        EGL.eglMakeCurrent(self.egl_display, self.egl_surface, self.egl_surface, self.egl_context)
        EGL.eglSwapInterval(self.egl_display, 0)  # never block in swap; the app paces frames itself

    def _destroy_surface(self):
        E = EGL
        E.eglMakeCurrent(self.egl_display, E.EGL_NO_SURFACE, E.EGL_NO_SURFACE, self.egl_context)  # surfaceless
        E.eglDestroySurface(self.egl_display, self.egl_surface)
        _wl_egl.wl_egl_window_destroy(self.egl_window)
        self.layer.destroy()
        self.surface.destroy()
        self.enter_serial = 0

    def _surface_enter(self, surface, output_proxy):
        o = next((o for o in self.outputs if _addr(o.proxy) == _addr(output_proxy)), None)
        if o and self.output is None:  # compositor picked the monitor: keep the saved spot on it
            self.output = o
            left, top = self._clamped(o, *self.margin)
            if [left, top] != self.margin:
                self.set_margin(left, top)
            if self.on_surface_changed:
                self.on_surface_changed()

    # ---- EGL ----------------------------------------------------------------
    def _init_egl(self):
        E = EGL
        self.egl_display = E.eglGetDisplay(ctypes.cast(_addr(self.display), E.EGLNativeDisplayType))
        major, minor = E.EGLint(), E.EGLint()
        if not E.eglInitialize(self.egl_display, ctypes.pointer(major), ctypes.pointer(minor)):
            raise RuntimeError("eglInitialize failed")
        E.eglBindAPI(E.EGL_OPENGL_API)  # desktop GL compatibility profile
        attrs = [E.EGL_SURFACE_TYPE, E.EGL_WINDOW_BIT, E.EGL_RENDERABLE_TYPE, E.EGL_OPENGL_BIT,
                 E.EGL_RED_SIZE, 8, E.EGL_GREEN_SIZE, 8, E.EGL_BLUE_SIZE, 8, E.EGL_ALPHA_SIZE, 8,
                 E.EGL_DEPTH_SIZE, 0, E.EGL_STENCIL_SIZE, 0, E.EGL_SAMPLES, 0, E.EGL_NONE]
        self.egl_config, count = E.EGLConfig(), E.EGLint()
        E.eglChooseConfig(self.egl_display, (E.EGLint * len(attrs))(*attrs), ctypes.pointer(self.egl_config), 1,
                          ctypes.pointer(count))
        if count.value < 1:
            raise RuntimeError("no RGBA8 EGL config")
        self.egl_context = E.eglCreateContext(self.egl_display, self.egl_config, E.EGL_NO_CONTEXT, None)

    def swap(self):
        EGL.eglSwapBuffers(self.egl_display, self.egl_surface)

    # ---- surface state ------------------------------------------------------
    def _configure(self, layer, serial, width, height):
        layer.ack_configure(serial)
        if width and height and (width, height) != (self.width, self.height):
            self.width, self.height = width, height
            if self.configured:
                _wl_egl.wl_egl_window_resize(self.egl_window, width, height, 0, 0)
        self.configured = True

    def set_margin(self, left, top):
        self.margin = [left, top]
        self.layer.set_margin(top, 0, 0, left)
        self.surface.commit()

    def set_geometry(self, left, top, width, height):
        """Move and resize in one commit (resizing from the left/top edge needs both).

        Never larger than the monitor, and kept fully on it.
        """
        out = self.output
        if out and out.w and out.h:
            width, height = min(width, out.w), min(height, out.h)
        if (width, height) != (self.width, self.height):
            self.width, self.height = width, height
            self.layer.set_size(width, height)
            _wl_egl.wl_egl_window_resize(self.egl_window, width, height, 0, 0)
        self.margin = list(self._clamped(out, left, top))
        self.layer.set_margin(self.margin[1], 0, 0, self.margin[0])
        self.surface.commit()

    def set_input_region(self, rects):
        """Only these (x, y, w, h) rectangles receive pointer input; applied on next swap."""
        region = self.compositor.create_region()
        for x, y, w, h in rects:
            region.add(int(x), int(y), int(w), int(h))
        self.surface.set_input_region(region)
        region.destroy()

    def set_cursor(self, shape):
        """shape: a wp_cursor_shape_device_v1 name such as 'default', 'pointer', 'ew_resize'."""
        if (shape, self.enter_serial) == getattr(self, "_cursor_sent", None):
            return
        self.cursor_shape = shape
        if self.cursor_device and self.enter_serial:
            self.cursor_device.set_shape(self.enter_serial, WpCursorShapeDeviceV1.shape[shape])
            self._cursor_sent = (shape, self.enter_serial)

    # ---- input --------------------------------------------------------------
    def _seat_caps(self, seat, caps):
        has_pointer, has_keyboard = caps & WlSeat.capability.pointer, caps & WlSeat.capability.keyboard
        if has_pointer and not self.pointer:
            p = self.pointer = seat.get_pointer()
            p.dispatcher["enter"] = self._ptr_enter
            p.dispatcher["leave"] = lambda *_: self.on_leave and self.on_leave()
            p.dispatcher["motion"] = lambda ptr, t, x, y: self.on_motion and self.on_motion(x, y)
            p.dispatcher["button"] = self._ptr_button
            p.dispatcher["axis"] = self._ptr_axis
            p.dispatcher["axis_discrete"] = self._ptr_axis_discrete
            p.dispatcher["frame"] = self._ptr_frame
            if self.cursor_manager:
                self.cursor_device = self.cursor_manager.get_pointer(p)
        if has_keyboard and not self.keyboard:
            k = self.keyboard = seat.get_keyboard()
            k.dispatcher["keymap"] = self._kb_keymap
            k.dispatcher["leave"] = lambda *_: setattr(self, "held", None)
            k.dispatcher["key"] = self._kb_key
            k.dispatcher["modifiers"] = lambda kb, serial, d, la, lo, g: self.xkb.update_mods(d, la, lo, g)
            k.dispatcher["repeat_info"] = self._kb_repeat_info

    def _ptr_enter(self, ptr, serial, surface, x, y):
        self.enter_serial = serial
        self.set_cursor(self.cursor_shape or "default")
        if self.on_motion:
            self.on_motion(x, y)

    def _ptr_button(self, ptr, serial, t, button, state):
        if self.on_button:
            self.on_button(button, state == 1)

    def _ptr_axis(self, ptr, t, axis, value):
        if axis == 0:
            self.scroll_px += value

    def _ptr_axis_discrete(self, ptr, axis, discrete):
        if axis == 0:
            self.scroll_discrete += discrete

    def _ptr_frame(self, ptr):
        # Wheel: one step per notch. Touchpad: one step per ~15px of travel.
        steps = -self.scroll_discrete if self.scroll_discrete else -int(self.scroll_px / 15)
        if self.scroll_discrete or steps:
            self.scroll_px = 0.0
        self.scroll_discrete = 0
        if steps and self.on_scroll:
            self.on_scroll(steps)

    def _kb_keymap(self, kb, fmt, fd, size):
        try:
            if fmt == 1:  # xkb_v1
                with mmap.mmap(fd, size, mmap.MAP_PRIVATE, mmap.PROT_READ) as m:
                    self.xkb.set_keymap(m[:size].rstrip(b"\0"))
        finally:
            os.close(fd)

    def _kb_repeat_info(self, kb, rate, delay):
        self.repeat_rate, self.repeat_delay = rate, delay / 1000

    def _kb_key(self, kb, serial, t, key, state):
        pressed = state == 1
        if pressed:
            self._emit_key(key)
            self.held = (key, time.perf_counter() + self.repeat_delay) if self.repeat_rate and self.xkb.repeats(key) else None
        elif self.held and self.held[0] == key:
            self.held = None
        if not pressed and self.on_key:
            self.on_key(key, False)

    def _emit_key(self, key):
        if self.on_key:
            self.on_key(key, True)
        text = self.xkb.text(key)
        if text and text.isprintable() and self.on_text:
            self.on_text(text)

    # ---- loop ---------------------------------------------------------------
    def pump(self, timeout):
        """Dispatch Wayland events, sleeping up to `timeout` seconds for new ones."""
        if self.lost:  # our monitor was unplugged: come back on whichever one the compositor picks
            self.lost = False
            self.move_to_output(None, *self.margin)
        d = _addr(self.display)
        while _wl.wl_display_prepare_read(d) != 0:
            _wl.wl_display_dispatch_pending(d)
        _wl.wl_display_flush(d)
        if self.held:  # wake in time for key repeat
            timeout = min(timeout, max(0.0, self.held[1] - time.perf_counter()))
        readable, _, _ = select.select([self.display.get_fd()], [], [], max(0.0, timeout))
        if readable:
            _wl.wl_display_read_events(d)
        else:
            _wl.wl_display_cancel_read(d)
        _wl.wl_display_dispatch_pending(d)
        if self.held and time.perf_counter() >= self.held[1]:
            key = self.held[0]
            self.held = (key, time.perf_counter() + 1.0 / self.repeat_rate)
            self._emit_key(key)

    def destroy(self):
        E = EGL
        E.eglMakeCurrent(self.egl_display, E.EGL_NO_SURFACE, E.EGL_NO_SURFACE, E.EGL_NO_CONTEXT)
        E.eglDestroySurface(self.egl_display, self.egl_surface)
        E.eglDestroyContext(self.egl_display, self.egl_context)
        _wl_egl.wl_egl_window_destroy(self.egl_window)
        E.eglTerminate(self.egl_display)
        self.layer.destroy()
        self.surface.destroy()
        self.display.flush()
        self.display.disconnect()
