"""The UI layer over her: the side buttons, the resize arrows, the bubbles and whichever
card is open, drawn with Pillow into one RGBA layer. Each card draws itself (its view in
kawaii/cards/views); the system monitor has its own small layer (monitor_view).

The layer is re-rendered only when something visible changes (typing, hover,
toggling); the render loop just blends the cached texture, so the UI costs
nothing per frame beyond one textured quad.
"""

from PIL import Image, ImageDraw

from kawaii.cards.views import VIEWS
from kawaii.render import bubbles, monitor_view
from kawaii.render.painter import (ACCENT, ALERT, BUTTON_H, BUTTON_STEP, CARD, GOOD, HANDLE_R, INK, NOTES_H,
                                   PANEL_W, PINK, PRI, SOFT, TINT, TOP_BAR, Painter)

ORDER = ("pendings", "calendar", "prs", "decoder", "picker", "settings", "observe", "rules")  # one is open at a time


class Overlay(Painter):
    """Lays out and paints the UI; also answers hit tests in window coordinates."""

    def __init__(self, model_w, model_h, px, left=PANEL_W):
        super().__init__(px)
        self.resize(model_w, model_h, left)
        self.buttons = [("pendings", "Pendings"), ("calendar", "Calendar"), ("observe", "Observability"),
                        ("rules", "Business Rules")]  # Think is hidden for now; its handler stays
        self.moves = []  # [{"name": group, "moves": [[expression, label], ...]}, ...]
        # Mini buttons under the big ones: animations, and the tools' cards.
        self.actions = [("decode", "Decode"), ("review", "PR Review"), ("settings", "Settings")]
        self.show_handles = False

    def resize(self, model_w, model_h, left=None):
        """left: width of the button column (PANEL_W), or 0 on portrait screens where the
        buttons float beside her head instead of taking a column."""
        if left is not None:
            self.left = left
        self.model_w = model_w
        self.w = self.left + model_w
        self.h = NOTES_H + model_h

    def handle_rects(self):
        """Resize arrows in the middle of each side of her area: name -> (x0, y0, x1, y1)."""
        r = HANDLE_R
        mid_x = self.left + self.model_w / 2
        mid_y = NOTES_H + (self.h - NOTES_H) / 2
        centers = {"left": (self.left + r + 2, mid_y), "right": (self.w - r - 2, mid_y),
                   "top": (mid_x, TOP_BAR + r + 2), "bottom": (mid_x, self.h - r - 2)}  # top: under the monitor pill
        return {name: (cx - r, cy - r, cx + r, cy + r) for name, (cx, cy) in centers.items()}

    def render_monitor(self, mon):
        """The system monitor's own layer: (premultiplied bytes, (x, y, w, h))."""
        return monitor_view.render(self, mon)

    def render(self, cards, talk_left=None, active_moves=(), moves_open=True, dancing=False, pose_label=None,
               actions_on=None, alerts=(), monitor=None, voice=None, thinking=False, gh_badge=None):
        """Return the layer as premultiplied RGBA bytes, rows top to bottom.

        cards: each card's payload by name (see ORDER); the open one is drawn by its view,
        and the closed ones still give the side buttons their badges.
        talk_left: whole seconds of talking left, or None when she is quiet.
        active_moves: expression names currently on (their mini buttons light up).
        alerts: bubbles to show above her head [{id, label, title, action}], first one shown.
        monitor: system monitor state for the top-right pill, or None.
        voice: {state, text, error, command} for the mic button and its banner, or None.
        thinking: the Think pose is on.
        gh_badge: a function giving (x, y) of the floating GitHub badge (drawn by the effects), to
        make it clickable; called once the cards are laid out, since it moves out of their way.
        """
        is_open = {name: bool(cards.get(name, {}).get("open")) for name in ORDER}
        img = Image.new("RGBA", (round(self.w * self.px), round(self.h * self.px)), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        self.begin_frame(img)
        self._handles(d)  # first: buttons drawn later sit on top and win clicks where they overlap

        y = self._buttons(d, cards, is_open, talk_left, dancing, pose_label, thinking,
                          self._column_height(active_moves, moves_open))
        on = dict(actions_on or {}, decode=is_open["decoder"], review=is_open["picker"], settings=is_open["settings"])
        y = self._actions(d, y, on)
        if self.moves:
            self._moves(d, y, active_moves, moves_open)
        if monitor:  # click areas only (painted separately by render_monitor); before the cards
            pill, panel = monitor_view.rects(self, monitor)
            self.regions.append(("monitor_toggle", None, pill))
            if panel:
                self.regions.append(("monitor_panel", None, panel))
        current = next((name for name in ORDER if is_open[name]), None)
        if current:  # after the arrows, so the card covers (and wins clicks over) the top one
            VIEWS[current].draw(self, d, cards[current])
        if alerts and not is_open["calendar"]:  # the calendar lists them itself
            bubbles.alert(self, d, alerts)
        if gh_badge:  # over the cards: the badge floats on top of everything
            x, y = gh_badge()
            self.regions.append(("gh_badge", None, (x - 27, y - 32, x + 27, y + 30)))
        if voice:  # last: its Run/Cancel must never be covered
            bubbles.voice(self, d, voice)
        self.footer(d, VIEWS[current].FOOTER if current else "Esc  ·  close")
        return img.convert("RGBa").tobytes()

    def _buttons(self, d, cards, is_open, talk_left, dancing, pose_label, thinking, column_h):
        """The big side buttons beside her head, top aligned with it; slid up when the column
        would run into the footer (the space above her head on that side is free). Returns
        the next free y."""
        head = self.head_y if self.head_y is not None else NOTES_H + 16
        y = max(TOP_BAR + 2, min(head, self.h - 38 - column_h))  # clear of the mic
        for name, label in self.buttons:
            rect = (12, y, PANEL_W - 12, y + BUTTON_H)
            active = {"talk": talk_left is not None, "dance": dancing, "pose": pose_label is not None,
                      "think": thinking}.get(name, is_open.get(name))
            if name == "talk" and active:
                label = f"Talking · {talk_left}s"
            elif name == "dance" and active:
                label = "Dancing · stop"
            elif name == "pose" and active:
                label = pose_label
            elif name == "think" and active:
                label = "Hmm… · got it"
            hovered = self.hover == ("button", name)
            fg = INK
            if self.flash == ("button", name):  # the impact frame: inverted, no shadow
                self.box(self.pressed("button", name, rect), INK, shadow=0)
                fg = CARD
            else:
                self.box(self.pressed("button", name, rect), PRI if active else TINT if hovered else CARD)
            d.text(self.s(rect[0] + 14, (rect[1] + rect[3]) / 2), label, font=self.f_button, fill=(*fg, 255),
                   anchor="lm")
            badge = self._badge(name, cards)
            if badge and badge[0]:  # how many wait: open pendings, due reminders, endpoints, companies
                cx, cy = rect[2] - 16, (rect[1] + rect[3]) / 2
                if name in ("observe", "rules"):  # their labels are long: the badge sits on the corner
                    cx, cy = rect[2] - 4, rect[1] + 2
                self.circle(cx, cy, 10, badge[1], edge=1.8)
                d.text(self.s(cx, cy), str(badge[0]), font=self.f_mini, anchor="mm", fill=(255, 255, 255, 255))
            self.regions.append(("button", name, rect))
            y += BUTTON_STEP
        return y

    @staticmethod
    def _badge(name, cards):
        """(count, colour) for a side button's badge, or None."""
        card = cards.get(name)
        if not card:
            return None
        if name == "pendings":
            return card["pendings"].open_count, PINK
        if name == "calendar":
            return card.get("due_count", 0), ALERT
        if name == "observe":  # endpoints registered: green while all answer
            eps = card["endpoints"]
            return len(eps), ALERT if any(e.get("ok") is False for e in eps) else GOOD
        if name == "rules":  # companies with rules written down
            return len(card["companies"]), ACCENT
        return None

    def _column_height(self, active, opened):
        """Height of the whole left column (big buttons, actions, moves) as drawn below."""
        rows = lambda n: (n + 1) // 2  # noqa: E731  two per row
        h = len(self.buttons) * BUTTON_STEP + rows(len(self.actions)) * 34
        if self.moves:
            h += 22
            if opened:
                h += 4 + sum(18 + rows(len(g["moves"])) * 26 + 2 for g in self.moves) + (22 if active else 0)
        return h

    def _actions(self, d, y, on):
        """A row of mini buttons for animated actions (walk, greet); returns the next free y."""
        x0, x1 = 12, PANEL_W - 12
        col_w, row_h = (x1 - x0 - 4) / 2, 28
        for i, (name, label) in enumerate(self.actions):
            bx = x0 + (i % 2) * (col_w + 4)
            rect = (bx, y, bx + col_w, y + row_h)
            hovered = self.hover == ("action", name)
            self.box(self.pressed("action", name, rect), PRI if on.get(name) else TINT if hovered else CARD,
                      radius=10, edge=2, shadow=2.5)
            d.text(self.s((rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2), label, font=self.f_mini,
                   fill=(*INK, 255), anchor="mm")
            self.regions.append(("action", name, rect))
            if i % 2 or i == len(self.actions) - 1:
                y += row_h + 6
        return y

    def _moves(self, d, y, active, opened):
        """Mini buttons for every expression, in two columns under the big buttons.
        A 'Moves' header collapses them (they can cover her arm on narrow screens)."""
        ink = (*INK, 255)
        x0, x1 = 12, PANEL_W - 12
        col_w, row_h, gap = (x1 - x0 - 4) / 2, 22, 4

        header = (x0, y, x1, y + 22)
        self.box(header, TINT if self.hover == ("moves_toggle", None) else CARD, radius=11, edge=2, shadow=2)
        d.text(self.s(x0 + 12, y + 11), f"Moves ({len(active)} on)" if active else "Moves", font=self.f_mini,
               fill=ink, anchor="lm")
        cx, cy = x1 - 14, y + 11  # open/closed chevron, drawn (fonts may lack the glyph)
        tri = (cx - 4, cy - 2, cx + 4, cy - 2, cx, cy + 3) if opened else (cx - 2, cy - 4, cx - 2, cy + 4, cx + 3, cy)
        self.poly(tri, INK)
        self.regions.append(("moves_toggle", None, header))
        if not opened:
            return
        y += 22 + gap

        for group in self.moves:
            # Group name on its own small ink tag, so it reads on any wallpaper.
            name = group["name"].upper()
            tw = self.f_mini.getlength(name) / self.px
            self.box((x0, y, x0 + tw + 14, y + 15), INK, radius=7, edge=0, shadow=0)
            d.text(self.s(x0 + 7, y + 7.5), name, font=self.f_mini, fill=(*SOFT, 255), anchor="lm")
            self.regions.append(("tag", None, (x0, y, x0 + tw + 14, y + 15)))
            y += 18
            for i, (exp, label) in enumerate(group["moves"]):
                bx = x0 + (i % 2) * (col_w + 4)
                rect = (bx, y, bx + col_w, y + row_h)
                on = exp in active
                hovered = self.hover == ("move", exp)
                self.box(self.pressed("move", exp, rect), PRI if on else TINT if hovered else CARD,
                          radius=8, edge=2, shadow=2)
                d.text(self.s((rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2), label, font=self.f_mini,
                       fill=ink, anchor="mm")
                self.regions.append(("move", exp, rect))
                if i % 2 or i == len(group["moves"]) - 1:
                    y += row_h + gap
            y += 2

        if active:  # one click to undo them all
            rect = (x0, y, x1, y + row_h)
            self.box(rect, TINT if self.hover == ("move", None) else CARD, radius=8, edge=2, shadow=2)
            d.text(self.s((x0 + x1) / 2, y + row_h / 2), "Clear all", font=self.f_mini, fill=ink, anchor="mm")
            self.regions.append(("move", None, rect))

    def _handles(self, d):
        ink = (*INK, 255)
        lw = max(1, round(2 * self.px))
        for name, (x0, y0, x1, y1) in self.handle_rects().items():
            self.regions.append(("handle", name, (x0, y0, x1, y1)))
            if not self.show_handles:
                continue  # still clickable, just not drawn until the pointer is over her
            hovered = self.hover == ("handle", name)
            cx, cy, a = (x0 + x1) / 2, (y0 + y1) / 2, HANDLE_R - 6
            self.circle(cx, cy, HANDLE_R, PRI if hovered else CARD, shadow=2)
            if name in ("left", "right"):  # double-headed horizontal arrow
                d.line(self.s(cx - a, cy, cx + a, cy), fill=ink, width=lw)
                d.line(self.s(cx - a + 4, cy - 4, cx - a, cy, cx - a + 4, cy + 4), fill=ink, width=lw)
                d.line(self.s(cx + a - 4, cy - 4, cx + a, cy, cx + a - 4, cy + 4), fill=ink, width=lw)
            else:  # double-headed vertical arrow
                d.line(self.s(cx, cy - a, cx, cy + a), fill=ink, width=lw)
                d.line(self.s(cx - 4, cy - a + 4, cx, cy - a, cx + 4, cy - a + 4), fill=ink, width=lw)
                d.line(self.s(cx - 4, cy + a - 4, cx, cy + a, cx + 4, cy + a - 4), fill=ink, width=lw)
