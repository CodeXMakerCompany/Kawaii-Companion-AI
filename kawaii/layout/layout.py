"""Her area on the desktop: where it sits and how big it is (per monitor, remembered), the
model's zoom/offset inside it (auto-fit from her pixels), her measured outline (for the
input region), and moving/resizing her by dragging."""

import time

from kawaii.layout import geometry
from kawaii.render.painter import NOTES_H, PANEL_W

DEFAULT_MARGIN = [80, 80]


class Layout:
    def __init__(self, model, win, store, left=PANEL_W, size=(420, 620), default_size=(420, 620),
                 fixed_scale=None, snapshot=False, now=time.perf_counter):
        self.model, self.win, self.store, self.now = model, win, store, now
        self.default_size, self.fixed_scale, self.snapshot = default_size, fixed_scale, snapshot
        self.left = left  # button column width: PANEL_W on wide screens, 0 on portrait ones
        self.size = tuple(size)  # her area
        self.drawn = (self.size, left)  # what the model and overlay were last sized for
        self.pending_geometry = None  # (left, top, w, h) to apply at the next frame
        self.scale, self.offset = 1.0, (0.0, 0.0)
        self.fit_due, self.fit_passes = None, 0  # time of the next auto-fit pass
        self.output_name = None  # monitor the current layout belongs to
        self.silhouette = None  # input-region bands around her, from a readback
        self.body_box = None  # her left/right extent in her area (px), from the same readback
        self.head_y = None  # top of her head (window coords), from the same readback
        self.silhouette_due = None
        self.drag = None  # {"kind", "press", ...} while moving or resizing

    # -- the model inside her area

    def set_transform(self, scale, offset):
        self.scale, self.offset = scale, tuple(offset)
        self.model.SetScale(scale)
        self.model.SetOffset(*offset)

    def refresh_silhouette(self, delay=0.35):
        self.silhouette_due = self.now() + delay

    def request_fit(self, delay=0.15):
        if self.fixed_scale:
            self.set_transform(self.fixed_scale, (0.0, 0.0))
            self.refresh_silhouette()
            return
        self.fit_due, self.fit_passes = self.now() + delay, 0

    def zoom(self, steps):
        """Manual zoom around her centre; R refits."""
        self.set_transform(min(5.0, max(0.2, self.scale * (1.1 ** steps))), self.offset)
        self.refresh_silhouette()
        self.remember()

    def look_at(self, x, y):
        """She follows the pointer while it is over her area, else looks ahead."""
        mw, mh = self.size
        mx, my = x - self.left, y - NOTES_H
        self.model.Drag(*((mx, my) if 0 <= mx < mw and 0 <= my < mh else (mw / 2, mh / 2)))

    def room(self):
        return geometry.stroll_room(self.size, self.body_box)

    # -- per-monitor layouts

    def remember(self):
        """Store and save this monitor's layout right away."""
        if self.win.output and not self.snapshot:
            self.store.remember_layout(self.win.output.name, {
                "margin": list(self.win.margin), "model_size": list(self.size), "left": self.left,
                "scale": float(self.scale), "offset": [float(v) for v in self.offset]})

    def apply(self, output):
        """Switch to `output`'s remembered layout, or a fresh one that suits its shape."""
        self.output_name = output.name if output else None
        saved = self.store.layout_for(self.output_name)
        if saved:
            self.left = saved.get("left", PANEL_W)
            (mw, mh), margin = saved["model_size"], saved["margin"]
            self.set_transform(saved.get("scale", 1.0), saved.get("offset", (0.0, 0.0)))
            self.refresh_silhouette(0.2)
        elif geometry.is_portrait(output):  # tall screen: fill it, buttons float beside her head
            self.left = 0
            mw, mh, margin = output.w, output.h - NOTES_H, (0, 0)
            self.request_fit()
        else:
            self.left = PANEL_W
            (mw, mh), margin = self.default_size, self.win.margin
            self.request_fit()
        self.pending_geometry = (*margin, self.left + mw, NOTES_H + mh)

    def surface_changed(self):
        """The window landed on another monitor (or learned which one), or was shrunk to fit."""
        name = self.win.output.name if self.win.output else None
        if name != self.output_name:
            self.apply(self.win.output)
        elif (self.win.width - self.left, self.win.height - NOTES_H) != self.size:
            self.pending_geometry = (*self.win.margin, self.win.width, self.win.height)

    def apply_pending_geometry(self):
        """Coalesced resize: one relayout per frame however fast the pointer moves. True when
        her area changed, so the overlay and its texture must follow."""
        if not self.pending_geometry:
            return False
        geometry_, self.pending_geometry = self.pending_geometry, None
        self.win.set_geometry(*geometry_)
        self.size = (self.win.width - self.left, self.win.height - NOTES_H)  # the window may cap it to the monitor
        if (self.size, self.left) == self.drawn:
            return False
        self.drawn = (self.size, self.left)
        self.model.Resize(*self.size)
        self.set_transform(self.scale, self.offset)
        self.refresh_silhouette()
        return True

    # -- dragging

    def begin_drag(self, kind, press):
        """kind: "move", or the edge being resized ("left", "right", "top", "bottom")."""
        self.drag = {"kind": kind, "press": press, "start": self.size, "margin": tuple(self.win.margin)}
        if kind == "move":
            self.drag.update(g_press=self.win.local_to_global(*press), g_topleft=self.win.local_to_global(0, 0))

    def drag_to(self, x, y):
        drag = self.drag
        if drag["kind"] == "move":  # in desktop coords, so she can cross onto another monitor
            gx, gy = self.win.local_to_global(x, y)
            (gpx, gpy), (gtx, gty) = drag["g_press"], drag["g_topleft"]
            self.win.place(gtx + gx - gpx, gty + gy - gpy, gx, gy)
            return
        # Pointer coords are surface-local and the surface itself moves, so work in output
        # coords (applied margin + local) relative to where the press happened.
        (px, py), (sl, st), (sw, sh) = drag["press"], drag["margin"], drag["start"]
        dx = self.win.margin[0] + x - (sl + px)
        dy = self.win.margin[1] + y - (st + py)
        kind = drag["kind"]
        left, top, mw, mh = sl, st, sw, sh
        if kind == "right":
            mw = sw + dx
        elif kind == "bottom":
            mh = sh + dy
        elif kind == "left":
            mw = geometry.clamp_size(sw - dx, sh)[0]
            left = sl + (sw - mw)
        elif kind == "top":
            mh = geometry.clamp_size(sw, sh - dy)[1]
            top = st + (sh - mh)
        mw, mh = geometry.clamp_size(mw, mh)
        self.pending_geometry = (max(0, int(left)), max(0, int(top)), self.left + mw, NOTES_H + mh)

    def end_drag(self):
        """None when nothing was dragged, else whether she was resized (and refitted)."""
        if not self.drag:
            return None
        resized = self.drag["kind"] != "move"
        self.drag = None
        self.request_fit() if resized else self.refresh_silhouette()
        self.remember()
        return resized

    # -- measuring her pixels

    def measurement_due(self, now, still):
        """Moving poses would mislead both the fit and the outline."""
        due = lambda t: t is not None and now >= t  # noqa: E731
        return still and (due(self.fit_due) or due(self.silhouette_due))

    def measure(self, alpha, now):
        """One readback of her coverage mask: a fit pass if one is due, else her outline.
        Returns True when the outline (and her head height) was re-measured."""
        if self.fit_due is not None and now >= self.fit_due:
            scale, offset, clipped = geometry.fit_transform(alpha, self.scale, self.offset)
            self.set_transform(scale, offset)
            self.fit_passes += 1
            more = self.fit_passes < 2 or (clipped and self.fit_passes < 6)
            self.fit_due = now + 0.05 if more else None
            if not more:
                self.refresh_silhouette(0.05)
                self.remember()
            return False
        self.silhouette = geometry.silhouette_rects(alpha, self.left, NOTES_H)
        self.body_box = geometry.body_box(alpha)
        row = geometry.top_row(alpha)
        self.head_y = NOTES_H + row if row is not None else None
        self.silhouette_due = None
        return True

    def body_region(self, dancing):
        """Her part of the input region; while dancing her outline keeps moving, so her whole area."""
        return (not dancing and self.silhouette) or [(self.left, NOTES_H, *self.size)]
