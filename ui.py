"""Side buttons, the Pendings card, the calendar and reminder bubble, drawn with Pillow
into one RGBA layer.

The layer is re-rendered only when something visible changes (typing, hover,
toggling); the render loop just blends the cached texture, so the UI costs
nothing per frame beyond one textured quad.

The look is Sakuga VFX's (github.com/finktheartist/sakuga-vfx, MIT): white cards with an
inked edge and a hard lavender shadow, bold italic labels, violet when switched on. The
click effects in fx.py use the same palette.
"""

import calendar
import datetime
import functools
import json
import subprocess
import uuid

from PIL import Image, ImageDraw, ImageFont

PANEL_W = 150  # left button column
NOTES_H = 230  # space above her head for the card
HANDLE_R = 14  # resize arrow radius
TOP_BAR = 38  # strip kept free at the top for the system monitor pill

CARD = (255, 255, 255)
INK = (29, 26, 74)  # text and every inked edge
SOFT = (184, 179, 255)  # the hard shadow under cards and buttons
PRI = (143, 141, 247)  # fill of whatever is on or selected
ACCENT = (90, 79, 216)  # accent text, and the outline of the effects
PINK = (255, 95, 168)  # badges, the effects' wedges and needles
MUTED = (133, 128, 176)
TINT = (240, 239, 255)  # hovered rows and buttons
TRACK = (201, 203, 224)
ALERT = (226, 76, 76)  # due reminders


@functools.lru_cache(maxsize=256)
def box_sprite(w, h, radius, fill, edge, shadow, line=INK, shade=SOFT):
    """A rounded box with an inked edge and a hard offset shadow, antialiased (drawn at 4x
    and scaled down). Sizes in image pixels; the image is (w + shadow x, h + shadow y)."""
    k = 4
    sx, sy = shadow
    img = Image.new("RGBA", ((w + sx) * k, (h + sy) * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if sx or sy:
        d.rounded_rectangle((sx * k, sy * k, (sx + w) * k - 1, (sy + h) * k - 1), radius * k, fill=shade)
    if edge:
        d.rounded_rectangle((0, 0, w * k - 1, h * k - 1), radius * k, fill=line)
    e = round(edge * k)
    d.rounded_rectangle((e, e, w * k - 1 - e, h * k - 1 - e), max(0, radius * k - e), fill=fill)
    return img.resize((w + sx, h + sy), Image.LANCZOS)


@functools.lru_cache(maxsize=64)
def poly_sprite(points, fill):
    """An antialiased polygon; points relative to its own top-left, in image pixels."""
    k = 4
    w = max(x for x, _ in points) + 1
    h = max(y for _, y in points) + 1
    img = Image.new("RGBA", (round(w * k), round(h * k)), (0, 0, 0, 0))
    ImageDraw.Draw(img).polygon([(x * k, y * k) for x, y in points], fill=fill)
    return img.resize((max(1, round(w)), max(1, round(h))), Image.LANCZOS)


def find_font(pattern):
    try:
        out = subprocess.run(["fc-match", "-f", "%{file}", pattern], capture_output=True, text=True, timeout=2)
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def load_font(pattern, size):
    path = find_font(pattern)
    try:
        return ImageFont.truetype(path, size) if path else ImageFont.load_default(size)
    except OSError:
        return ImageFont.load_default(size)


class Events:
    """Dated reminders saved as JSON. A one-off is due from its date until marked done, so
    a missed day keeps reminding instead of silently passing.

    A yearly one comes back every year on its month/day: marking it done completes that
    year's occurrence. Occurrences before it was made yearly (`since`) never count, so
    adding an anniversary whose day already passed this year waits for next year.
    """

    def __init__(self, path):
        self.path = path
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            data = {}
        self.items = []
        for e in data.get("events", []):
            try:
                datetime.date.fromisoformat(e["date"])
                self.items.append({"id": str(e.get("id") or uuid.uuid4().hex), "date": e["date"],
                                   "title": str(e["title"]), "done": bool(e.get("done")),
                                   "yearly": bool(e.get("yearly")), "done_year": e.get("done_year"),
                                   "since": e.get("since") or datetime.date.today().isoformat()})
            except (KeyError, TypeError, ValueError):
                continue

    def save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"events": self.items}, ensure_ascii=False, indent=1))
        except OSError:
            pass

    def get(self, event_id):
        return next((e for e in self.items if e["id"] == event_id), None)

    @staticmethod
    def _on(year, base):
        """`base`'s month/day in `year` (29 Feb falls back to 28 Feb in common years)."""
        try:
            return base.replace(year=year)
        except ValueError:
            return base.replace(year=year, day=28)

    def when(self, e, today):
        """The date that matters now: a one-off's date; for a yearly one, this year's
        occurrence while it is waiting (upcoming or overdue), otherwise next year's."""
        base = datetime.date.fromisoformat(e["date"])
        if not e["yearly"]:
            return base
        occ = self._on(today.year, base)
        if (e["done_year"] or 0) >= today.year or occ.isoformat() < e["since"]:
            occ = self._on(today.year + 1, base)
        return occ

    def is_done(self, e):
        return e["done"] and not e["yearly"]

    def add(self, date, title, yearly=False):
        self.items.append({"id": uuid.uuid4().hex, "date": date, "title": title, "done": False, "yearly": yearly,
                           "done_year": None, "since": datetime.date.today().isoformat()})
        self.save()

    def update(self, event_id, date, title, yearly=None):
        e = self.get(event_id)
        if e:
            changed = date != e["date"] or (yearly is not None and yearly != e["yearly"])
            e.update(date=date, title=title)
            if yearly is not None:
                e["yearly"] = yearly
            if changed:  # a new date or rhythm starts fresh from today
                e.update(done=False, done_year=None, since=datetime.date.today().isoformat())
            self.save()

    def remove(self, event_id):
        self.items = [e for e in self.items if e["id"] != event_id]
        self.save()

    def toggle_done(self, event_id, today=None):
        """One-off: flip done. Yearly: complete the occurrence that is currently waiting."""
        e = self.get(event_id)
        if not e:
            return
        if e["yearly"]:
            e["done_year"] = self.when(e, today or datetime.date.today()).year
        else:
            e["done"] = not e["done"]
        self.save()

    def due(self, today):
        """Waiting today or earlier, oldest first."""
        due = [e for e in self.items if not self.is_done(e) and self.when(e, today) <= today]
        return sorted(due, key=lambda e: self.when(e, today))

    def listing(self, today):
        """Due first, then upcoming by date, then finished one-offs (most recent first)."""
        due = self.due(today)
        upcoming = sorted((e for e in self.items if not self.is_done(e) and self.when(e, today) > today),
                          key=lambda e: self.when(e, today))
        done = sorted((e for e in self.items if self.is_done(e)), key=lambda e: e["date"], reverse=True)
        return due + upcoming + done

    def marked_days(self, year):
        """ISO dates with a reminder still to do, around `year` (yearly ones on every year)."""
        days = set()
        for e in self.items:
            if self.is_done(e):
                continue
            if e["yearly"]:
                base = datetime.date.fromisoformat(e["date"])
                days.update(self._on(y, base).isoformat() for y in (year - 1, year, year + 1))
            else:
                days.add(e["date"])
        return days


class Pendings:
    """Today's pending list, saved as JSON. Unfinished items carry over to a new day."""

    def __init__(self, path):
        self.path = path
        self.date = None
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            data = {}
        self.items = [
            {"text": str(i["text"]), "done": bool(i.get("done"))}
            for i in data.get("items", []) if isinstance(i, dict) and i.get("text")
        ]
        self.date = data.get("date")
        self.roll_day()

    def roll_day(self):
        today = datetime.date.today().isoformat()
        if self.date != today:
            self.items = [i for i in self.items if not i["done"]]
            self.date = today
            self.save()

    def save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"date": self.date, "items": self.items}, ensure_ascii=False, indent=1))
        except OSError:
            pass

    @property
    def open_count(self):
        return sum(not i["done"] for i in self.items)

    def add(self, text):
        self.items.append({"text": text, "done": False})
        self.save()

    def toggle(self, index):
        self.items[index]["done"] = not self.items[index]["done"]
        self.save()

    def remove(self, index):
        del self.items[index]
        self.save()


class Overlay:
    """Lays out and paints the UI; also answers hit tests in window coordinates."""

    def __init__(self, model_w, model_h, px, left=PANEL_W):
        self.px = px
        self.head_y = None  # top of her head in window coords, once measured
        self.origin = (0, 0)  # drawing origin (window coords) of the image being painted
        self.resize(model_w, model_h, left)
        self.f_button = load_font("sans:bold:italic", round(15 * px))
        self.f_mini = load_font("sans:bold:italic", round(11 * px))  # mini buttons
        self.f_title = load_font("sans:bold:italic", round(15 * px))
        self.f_item = load_font("sans", round(15 * px))
        self.f_hint = load_font("sans", round(11 * px))
        self.f_day = load_font("sans", round(13 * px))
        self.f_day_bold = load_font("sans:bold", round(13 * px))
        self.buttons = [("pendings", "Pendings"), ("calendar", "Calendar"), ("talk", "Talk"), ("dance", "Dance"),
                        ("pose", "Pose")]
        self.moves = []  # [{"name": group, "moves": [[expression, label], ...]}, ...]
        self.actions = [("walk", "Walk"), ("greet", "Greet")]  # animated, not toggled expressions
        self.hover = None
        self.show_handles = False
        self.regions = []
        self.squash = {}  # (kind, name) -> (x scale, y scale) of buttons being pressed (fx.Press)
        self.flash = None  # (kind, name) of a button drawn inverted for an instant: the impact frame
        self.caret = None  # (x, y) of the text caret in the open card, for typing effects
        self._img = None  # the image being painted

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

    def s(self, *values):
        """Window coords -> image pixels (x, y pairs shifted by the drawing origin)."""
        ox, oy = self.origin
        return [round((v - (oy if i % 2 else ox)) * self.px) for i, v in enumerate(values)]

    def rect_of(self, kind, index=None):
        """Window rect of an element as last drawn, or None."""
        for k, i, rect in self.regions:
            if k == kind and i == index:
                return rect
        return None

    def _pressed(self, kind, name, rect):
        """rect squashed around its centre while its button springs back from a press."""
        s = self.squash.get((kind, name))
        if not s:
            return rect
        cx, cy = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
        hw, hh = (rect[2] - rect[0]) / 2 * s[0], (rect[3] - rect[1]) / 2 * s[1]
        return cx - hw, cy - hh, cx + hw, cy + hh

    def _paste(self, sprite, x, y):
        """Blend a sprite onto the image being painted, its top-left at image pixel (x, y)."""
        cx, cy = max(0, -x), max(0, -y)  # cropped where it hangs off the top or left edge
        if cx or cy:
            if cx >= sprite.width or cy >= sprite.height:
                return
            sprite = sprite.crop((cx, cy, sprite.width, sprite.height))
        self._img.alpha_composite(sprite, (x + cx, y + cy))

    def _box(self, rect, fill=CARD, radius=12, edge=2.5, shadow=4):
        """A Sakuga box at rect (window coords): inked edge, hard shadow down and right."""
        x0, y0, x1, y1 = self.s(*rect)
        if x1 <= x0 or y1 <= y0:
            return
        sh = (round(shadow * self.px), round(shadow * 7 / 6 * self.px))
        self._paste(box_sprite(x1 - x0, y1 - y0, round(radius * self.px), tuple(fill[:3]), edge * self.px, sh),
                    x0, y0)

    def _circle(self, cx, cy, r, fill=CARD, edge=2.0, shadow=0):
        self._box((cx - r, cy - r, cx + r, cy + r), fill, radius=r, edge=edge, shadow=shadow)

    def _poly(self, points, fill):
        """An antialiased polygon from window-coord x, y pairs."""
        pts = self.s(*points)
        xs, ys = pts[0::2], pts[1::2]
        x0, y0 = min(xs), min(ys)
        self._paste(poly_sprite(tuple((x - x0, y - y0) for x, y in zip(xs, ys)), (*fill[:3], 255)), x0, y0)

    def _panel(self, rect, tail_x=None, tail=12):
        """A white card with an inked edge; tail_x: a speech-bubble tail under it there."""
        self._box(rect, radius=14, edge=2.5, shadow=5)
        if tail_x is not None:
            bottom = rect[3]
            self._poly((tail_x - 12, bottom - 2.5, tail_x + 12, bottom - 2.5, tail_x, bottom + tail + 2), INK)
            self._poly((tail_x - 8, bottom - 3, tail_x + 8, bottom - 3, tail_x, bottom + tail - 2.5), CARD)

    def _checkbox(self, bx, by, size, done):
        """A Sakuga checkbox: a white inked box, an ink tick when done."""
        self._box((bx, by, bx + size, by + size), radius=4, edge=1.8, shadow=0)
        if done:
            k = size / 15
            self._tick(bx + 3.5 * k, by + 8 * k, bx + 6.5 * k, by + 11 * k, bx + 12 * k, by + 4.5 * k)

    def _tick(self, *pts):
        ImageDraw.Draw(self._img).line(self.s(*pts), fill=(*INK, 255), width=max(1, round(2.4 * self.px)),
                                       joint="curve")

    def hit(self, x, y):
        for kind, index, (x0, y0, x1, y1) in reversed(self.regions):
            if x0 <= x < x1 and y0 <= y < y1:
                return kind, index
        return None

    def render(self, pendings, pendings_open, draft, talk_left=None, active_moves=(), moves_open=True,
               dancing=False, pose_label=None, actions_on=None, cal=None, alerts=(), monitor=None, voice=None):
        """Return the layer as premultiplied RGBA bytes, rows top to bottom.

        talk_left: whole seconds of talking left, or None when she is quiet.
        active_moves: expression names currently on (their mini buttons light up).
        cal: calendar state {open, month, selected, draft, editing, today, events}, or None.
        alerts: bubbles to show above her head [{id, label, title, action}], first one shown.
        monitor: system monitor state for the top-right pill, or None.
        voice: {state, text, error, command} for the mic button and its banner, or None.
        """
        cal = cal or {"open": False}
        img = Image.new("RGBA", (round(self.w * self.px), round(self.h * self.px)), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        self._img = img
        self.regions = []
        self.caret = None
        self._handles(d)  # first: buttons drawn later sit on top and win clicks where they overlap

        # Buttons beside her head, top aligned with it; slid up when the column would run
        # into the footer (the space above her head on that side is free).
        head = self.head_y if self.head_y is not None else NOTES_H + 16
        y = max(8, min(head, self.h - 38 - self._column_height(active_moves, moves_open)))
        for name, label in self.buttons:
            rect = (12, y, PANEL_W - 12, y + 38)
            active = {"pendings": pendings_open, "calendar": cal["open"], "talk": talk_left is not None,
                      "dance": dancing, "pose": pose_label is not None}[name]
            if name == "talk" and active:
                label = f"Talking · {talk_left}s"
            elif name == "dance" and active:
                label = "Dancing · stop"
            elif name == "pose" and active:
                label = pose_label
            hovered = self.hover == ("button", name)
            fg = INK
            if self.flash == ("button", name):  # the impact frame: inverted, no shadow
                self._box(self._pressed("button", name, rect), INK, shadow=0)
                fg = CARD
            else:
                self._box(self._pressed("button", name, rect), PRI if active else TINT if hovered else CARD)
            d.text(self.s(rect[0] + 14, (rect[1] + rect[3]) / 2), label, font=self.f_button, fill=(*fg, 255),
                   anchor="lm")
            due = cal.get("due_count", 0)
            badge = {"pendings": (pendings.open_count, PINK), "calendar": (due, ALERT)}.get(name)
            if badge and badge[0]:  # count of open pendings / reminders waiting to be marked done
                cx, cy = rect[2] - 16, (rect[1] + rect[3]) / 2
                self._circle(cx, cy, 10, badge[1], edge=1.8)
                d.text(self.s(cx, cy), str(badge[0]), font=self.f_mini, anchor="mm", fill=(255, 255, 255, 255))
            self.regions.append(("button", name, rect))
            y += 48

        y = self._actions(d, y, actions_on or {})
        if self.moves:
            self._moves(d, y, active_moves, moves_open)
        if monitor:  # click areas only (painted separately by render_monitor); before the cards
            pill, panel = self.monitor_rects(monitor)
            self.regions.append(("monitor_toggle", None, pill))
            if panel:
                self.regions.append(("monitor_panel", None, panel))
        self.card_top = None
        if pendings_open:  # after the arrows, so the card covers (and wins clicks over) the top one
            self._card(d, pendings, draft)
        elif cal["open"]:
            self._calendar(d, cal)
        if alerts and not cal["open"]:  # the calendar lists them itself
            self._alert(d, alerts)
        if voice:  # last: its Run/Cancel must never be covered
            self._voice(d, voice)
        self._footer(d, "Esc  ·  close" + (" the list" if pendings_open else " the calendar" if cal["open"] else ""))
        return img.convert("RGBa").tobytes()

    def _fit(self, text, font, width):
        """text, shortened with an ellipsis to fit `width` (window units)."""
        if font.getlength(text) <= width * self.px:
            return text
        while text and font.getlength(text + "…") > width * self.px:
            text = text[:-1]
        return text + "…"

    def _bubble_box(self, used, above=None):
        """Where a card of height `used` goes: tail on her head when there is room, else
        pinned under the top strip. `above` stacks it over another card instead."""
        tail = 12
        if above is not None:
            bottom = above - 8
            return max(TOP_BAR, bottom - used), max(TOP_BAR, bottom - used) + used, False
        head = self.head_y if self.head_y is not None else NOTES_H
        bottom = head - tail
        if bottom - used >= TOP_BAR:
            return bottom - used, bottom, True
        return TOP_BAR, TOP_BAR + used, False

    def _calendar(self, d, cal):
        """Month grid to pick a date, a title field, Add/Update and the reminder list."""
        ink = (*INK, 255)
        pad, cell_h, row_h = 12, 24, 22
        x0, x1 = self.left + 16, self.w - 16
        year, month = cal["month"]
        today = cal["today"]
        weeks = calendar.Calendar(0).monthdatescalendar(year, month)
        events = cal["events"]
        listing = events.listing(today)
        marked = events.marked_days(year)
        shown_rows = listing[:4]
        used = (pad + 26 + 16 + len(weeks) * cell_h + 8 + 30 + 6 + 28 + 10 + 16
                + max(1, len(shown_rows)) * row_h + (16 if len(listing) > len(shown_rows) else 0) + pad)
        top, bottom, tail = self._bubble_box(used)
        cx_tail = self.left + self.model_w / 2
        self._panel((x0, top, x1, bottom), cx_tail if tail else None)
        self.regions.append(("cal_card", None, (x0, top, x1, bottom + (12 if tail else 0))))
        self.card_top = top

        # Month header with prev/next arrows.
        y = top + pad
        d.text(self.s((x0 + x1) / 2, y + 13), datetime.date(year, month, 1).strftime("%B %Y"), font=self.f_title,
               fill=ink, anchor="mm")
        for kind, ax in (("cal_prev", x0 + pad), ("cal_next", x1 - pad - 26)):
            rect = (ax, y, ax + 24, y + 24)
            self._box(rect, TINT if self.hover == (kind, None) else CARD, radius=8, edge=2, shadow=2)
            mx, my = ax + 12, y + 12
            tri = (mx + 3, my - 5, mx + 3, my + 5, mx - 4, my) if kind == "cal_prev" else \
                (mx - 3, my - 5, mx - 3, my + 5, mx + 4, my)
            self._poly(tri, INK)
            self.regions.append((kind, None, rect))
        y += 26

        cw = (x1 - x0 - 2 * pad) / 7
        for i, name in enumerate(("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")):
            d.text(self.s(x0 + pad + i * cw + cw / 2, y + 7), name, font=self.f_hint, fill=(*MUTED, 255), anchor="mm")
        y += 16

        for week in weeks:
            for i, day in enumerate(week):
                iso = day.isoformat()
                rect = (x0 + pad + i * cw + 2, y + 1, x0 + pad + (i + 1) * cw - 2, y + cell_h - 1)
                selected, is_today = iso == cal["selected"], day == today
                if selected:
                    self._box(rect, PRI, radius=7, edge=2, shadow=0)
                elif self.hover == ("cal_day", iso):
                    self._box(rect, TINT, radius=7, edge=0, shadow=0)
                color = ink if selected else (*ACCENT, 255) if is_today else \
                    ink if day.month == month else (*MUTED, 255)
                font = self.f_day_bold if is_today else self.f_day
                cx, cy = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
                d.text(self.s(cx, cy - (2 if iso in marked else 0)), str(day.day), font=font, fill=color, anchor="mm")
                if iso in marked:  # a reminder to do on this day; red once it is due
                    dot = INK if selected else ALERT if iso <= today.isoformat() else ACCENT
                    self._circle(cx, cy + 8, 2.2, dot, edge=0)
                self.regions.append(("cal_day", iso, rect))
            y += cell_h
        y += 8

        # Selected date + title field.
        label = datetime.date.fromisoformat(cal["selected"]).strftime("%a %d %b")
        lw = self.f_title.getlength(label) / self.px
        d.text(self.s(x0 + pad, y + 13), label, font=self.f_title, fill=ink, anchor="lm")
        field = (x0 + pad + lw + 10, y, x1 - pad, y + 26)
        self._box(field, radius=8, edge=2, shadow=2)
        limit = field[2] - field[0] - 20
        shown = cal["draft"]
        while shown and self.f_item.getlength(shown) > limit * self.px:
            shown = shown[1:]
        tx, ty = field[0] + 10, y + 13
        if shown:
            d.text(self.s(tx, ty), shown, font=self.f_item, fill=(*INK, 255), anchor="lm")
        else:
            d.text(self.s(tx + 2, ty), self._fit("Reminder title", self.f_item, limit), font=self.f_item,
                   fill=(*MUTED, 255), anchor="lm")
        caret = tx + self.f_item.getlength(shown) / self.px + 1
        self.caret = (caret, ty)
        d.line(self.s(caret, ty - 8, caret, ty + 8), fill=ink, width=max(1, round(2 * self.px)))
        self.regions.append(("cal_input", None, field))
        y += 30 + 6

        # Add / Update, and while editing: New, Delete.
        editing = cal["editing"]
        bx = x0 + pad
        for kind, text, fill, color in (("cal_save", "Update" if editing else "Add reminder", PRI, INK),
                                        ("cal_new", "New", CARD, INK) if editing else (None,) * 4,
                                        ("cal_delete", "Delete", CARD, ALERT) if editing else (None,) * 4):
            if not kind:
                continue
            w = self.f_mini.getlength(text) / self.px + 28
            rect = (bx, y, bx + w, y + 26)
            self._box(self._pressed(kind, None, rect), TINT if self.hover == (kind, None) and fill == CARD else fill,
                      radius=10, edge=2, shadow=2.5)
            d.text(self.s(bx + w / 2, y + 13), text, font=self.f_mini, fill=(*color, 255), anchor="mm")
            self.regions.append((kind, None, rect))
            bx += w + 6
        # Yearly switch: a small track + knob, right-aligned on the same row.
        sw_x1 = x1 - pad
        label_w = self.f_hint.getlength("Yearly") / self.px
        track = (sw_x1 - 34, y + 6, sw_x1, y + 22)
        on = cal.get("yearly", False)
        self._box(track, PRI if on else TRACK, radius=8, edge=2, shadow=0)
        kx = track[2] - 9 if on else track[0] + 9
        self._circle(kx, y + 14, 6.5, CARD, edge=2)
        d.text(self.s(track[0] - 6, y + 14), "Yearly", font=self.f_hint, fill=ink, anchor="rm")
        self.regions.append(("cal_yearly", None, (track[0] - label_w - 10, y, sw_x1, y + 28)))
        y += 28 + 10

        # Reminder list: click edits, the box marks done, right-click deletes.
        d.text(self.s(x0 + pad, y + 6), "REMINDERS", font=self.f_hint, fill=(*MUTED, 255), anchor="lm")
        hint = "click: edit · right-click: delete"
        if self.f_hint.getlength(hint) / self.px + 90 < x1 - x0 - 2 * pad:
            d.text(self.s(x1 - pad, y + 6), hint, font=self.f_hint, fill=(*MUTED, 255), anchor="rm")
        y += 16
        if not shown_rows:
            d.text(self.s(x0 + pad, y + row_h / 2), "Pick a date, type a title, Add reminder", font=self.f_hint,
                   fill=(*MUTED, 255), anchor="lm")
        iso_today = today.isoformat()
        for e in shown_rows:
            row = (x0 + 6, y, x1 - 6, y + row_h)
            if e["id"] == editing or self.hover == ("cal_event", e["id"]):
                self._box(row, TINT, radius=6, edge=0, shadow=0)
            self.regions.append(("cal_event", e["id"], row))
            bx, by = x0 + pad, y + 4
            box = (bx - 2, by - 2, bx + 16, by + 16)
            finished = events.is_done(e)
            self._checkbox(bx, by, 14, finished)
            self.regions.append(("cal_done", e["id"], box))
            occ = events.when(e, today)
            due = not finished and occ <= today
            when = occ.strftime("%a %d %b") + ("" if occ.year == today.year else f" {occ.year % 100:02d}")
            d.text(self.s(bx + 22, y + row_h / 2), when, font=self.f_hint,
                   fill=(*ALERT, 255) if due else (*MUTED, 255) if finished else (*ACCENT, 255), anchor="lm")
            title_x = bx + 22 + 88
            tag_w = (self.f_hint.getlength("yearly") / self.px + 12) if e["yearly"] else 0
            title = self._fit(e["title"], self.f_day, x1 - pad - title_x - tag_w)
            color = (*MUTED, 255) if finished else ink
            d.text(self.s(title_x, y + row_h / 2), title, font=self.f_day, fill=color, anchor="lm")
            if e["yearly"]:  # small tag at the end of the row
                tx1 = x1 - pad
                self._box((tx1 - tag_w + 2, y + 3, tx1, y + row_h - 3), TINT, radius=7, edge=1.2, shadow=0)
                d.text(self.s(tx1 - (tag_w - 2) / 2, y + row_h / 2), "yearly", font=self.f_hint,
                       fill=(*ACCENT, 255), anchor="mm")
            if finished:
                d.line(self.s(title_x, y + row_h / 2, title_x + self.f_day.getlength(title) / self.px, y + row_h / 2),
                       fill=color, width=max(1, round(self.px)))
            y += row_h
        if len(listing) > len(shown_rows):
            d.text(self.s(x0 + pad + 22, y + 7), f"+{len(listing) - len(shown_rows)} more", font=self.f_hint,
                   fill=(*MUTED, 255), anchor="lm")

    def _alert(self, d, alerts):
        """The first waiting alert (reminder or system alarm) with its action button."""
        a = alerts[0]
        pad = 12
        x0, x1 = self.left + 16, self.w - 16
        action_w = self.f_mini.getlength(a["action"]) / self.px + 28
        lines = self._wrap(a["title"], self.f_title, x1 - x0 - 2 * pad - action_w - 14)[:2]
        used = pad + 16 + len(lines) * 20 + (14 if len(alerts) > 1 else 0) + pad
        top, bottom, tail = self._bubble_box(used, above=self.card_top)
        self._panel((x0, top, x1, bottom), self.left + self.model_w / 2 if tail else None)
        self._box((x0 + 6, top + 8, x0 + 10, bottom - 8), ALERT, radius=2, edge=0, shadow=0)
        self.regions.append(("alert", None, (x0, top, x1, bottom + (12 if tail else 0))))
        y = top + pad
        d.text(self.s(x0 + pad + 4, y + 6), a["label"], font=self.f_hint, fill=(*ALERT, 255), anchor="lm")
        y += 16
        for ln in lines:
            d.text(self.s(x0 + pad + 4, y + 10), ln, font=self.f_title, fill=(*INK, 255), anchor="lm")
            y += 20
        if len(alerts) > 1:
            d.text(self.s(x0 + pad + 4, y + 6), f"+{len(alerts) - 1} more waiting", font=self.f_hint,
                   fill=(*MUTED, 255), anchor="lm")
        rect = (x1 - pad - action_w, (top + bottom) / 2 - 15, x1 - pad, (top + bottom) / 2 + 15)
        self._box(rect, TINT if self.hover == ("alert_action", a["id"]) else PRI, radius=10, edge=2, shadow=2.5)
        d.text(self.s((rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2), a["action"], font=self.f_mini,
               fill=(*INK, 255), anchor="mm")
        self.regions.append(("alert_action", a["id"], rect))

    def _voice(self, d, v):
        """Mic button (top-left) and a banner with what she heard / is doing / Run-Cancel."""
        ink = (*INK, 255)
        state = v["state"]
        cx, cy, r = 25, 20, 13
        fill = {"listening": PINK, "thinking": (255, 200, 90), "confirm": PRI}.get(state)
        if fill is None:
            fill = TINT if self.hover == ("mic", None) else CARD
        self._circle(cx, cy, r, fill, shadow=2)
        lw = max(1, round(2 * self.px))
        self._box((cx - 3.5, cy - 8, cx + 3.5, cy + 2), INK, radius=3.5, edge=0, shadow=0)
        d.arc(self.s(cx - 7, cy - 6, cx + 7, cy + 5), start=0, end=180, fill=ink, width=lw)
        d.line(self.s(cx, cy + 5, cx, cy + 8), fill=ink, width=lw)
        d.line(self.s(cx - 4, cy + 8.5, cx + 4, cy + 8.5), fill=ink, width=lw)
        self.regions.append(("mic", None, (cx - r - 2, cy - r - 2, cx + r + 2, cy + r + 2)))

        text = v.get("text")
        if not text:
            return
        x0, x1, pad = 12, self.w - 12, 10
        confirm = state == "confirm" and v.get("command")
        h = 30 + (52 if confirm else 0)
        top = TOP_BAR + 2
        self._box((x0, top, x1, top + h), radius=12, edge=2.5, shadow=4)
        self.regions.append(("voice_banner", None, (x0, top, x1, top + h)))
        color = (*ALERT, 255) if v.get("error") else ink
        d.text(self.s(x0 + pad, top + 15), self._fit(text, self.f_hint, x1 - x0 - 2 * pad), font=self.f_hint,
               fill=color, anchor="lm")
        if not confirm:
            return
        y = top + 30
        self._box((x0 + pad, y, x1 - pad, y + 20), INK, radius=6, edge=0, shadow=0)
        d.text(self.s(x0 + pad + 8, y + 10), self._fit("$ " + v["command"], self.f_hint, x1 - x0 - 2 * pad - 16),
               font=self.f_hint, fill=(*SOFT, 255), anchor="lm")
        y += 24
        bx = x1 - pad
        for kind, label, base in (("voice_cancel", "Cancel", CARD), ("voice_run", "Run", PRI)):
            w = self.f_mini.getlength(label) / self.px + 26
            rect = (bx - w, y, bx, y + 22)
            self._box(rect, TINT if self.hover == (kind, None) else base, radius=8, edge=2, shadow=2)
            d.text(self.s(rect[0] + w / 2, y + 11), label, font=self.f_mini, fill=ink, anchor="mm")
            self.regions.append((kind, None, rect))
            bx -= w + 6
        d.text(self.s(x0 + pad, y + 11), "Run once to approve: it is then remembered", font=self.f_hint,
               fill=(*MUTED, 255), anchor="lm")

    def monitor_rects(self, mon):
        """Pill and (when open) panel rectangles. Fixed sizes, so changing numbers never
        move anything or need the main layer repainted."""
        w = self.f_hint.getlength("CPU 100%   GPU 100%   RAM 100%") / self.px + 40
        x1, y0 = self.w - 10, 8
        pill = (x1 - w, y0, x1, y0 + 24)
        if not mon["open"]:
            return pill, None
        pw = min(270, self.w - 20)
        ph = 12 + len(mon["rows"]) * 24 + (32 if mon.get("top") else 0) + 10
        return pill, (x1 - pw, y0 + 30, x1, y0 + 30 + ph)

    def render_monitor(self, mon):
        """Paint just the monitor into a small image: (premultiplied bytes, (x, y, w, h))."""
        pill, panel = self.monitor_rects(mon)
        box = (min(pill[0], panel[0]) if panel else pill[0], pill[1], pill[2] + 4, (panel[3] if panel else pill[3]) + 5)
        w, h = round((box[2] - box[0]) * self.px), round((box[3] - box[1]) * self.px)  # with the shadows
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        regions, self.origin, main = self.regions, (box[0], box[1]), self._img
        self._img = img
        try:
            self._monitor(ImageDraw.Draw(img), mon)
        finally:
            self.regions, self.origin, self._img = regions, (0, 0), main
        return img.convert("RGBa").tobytes(), (box[0], box[1], w, h)

    def _monitor(self, d, mon):
        """Top-right system pill (CPU/GPU/RAM + status dot); click for the detail panel."""
        ink = (*INK, 255)
        level_color = {"ok": (60, 180, 100), "warn": (215, 145, 20), "alarm": ALERT}  # readable on white
        chips = "   ".join(f"{k} {v}" for k, v in mon["pill"])
        rect, panel = self.monitor_rects(mon)
        y0 = rect[1]
        self._box(rect, TINT if self.hover == ("monitor_toggle", None) else CARD, radius=12, edge=2, shadow=2.5)
        self._circle(rect[0] + 14, y0 + 12, 4.5, level_color[mon["level"]], edge=1.5)
        d.text(self.s(rect[0] + 26, y0 + 12), chips, font=self.f_hint, fill=ink, anchor="lm")
        if not panel:
            return
        rows = mon["rows"]
        self._box(panel, radius=12, edge=2.5, shadow=4)
        y = panel[1] + 10
        bx0, bx1 = panel[0] + 12, panel[2] - 12
        for label, value, frac, level in rows:
            d.text(self.s(bx0, y + 7), label, font=self.f_hint, fill=(*MUTED, 255), anchor="lm")
            d.text(self.s(bx1, y + 7), value, font=self.f_hint, fill=(*level_color[level], 255) if level != "ok"
                   else ink, anchor="rm")
            if frac is not None:  # usage bar
                self._box((bx0, y + 15, bx1, y + 20), TRACK, radius=2.5, edge=0, shadow=0)
                fx = bx0 + (bx1 - bx0) * max(0.0, min(1.0, frac))
                if fx > bx0 + 5:
                    self._box((bx0, y + 15, fx, y + 20), level_color[level] if level != "ok" else PRI,
                              radius=2.5, edge=0, shadow=0)
            y += 24
        if mon.get("top"):
            d.text(self.s(bx0, y + 6), "TOP PROCESS", font=self.f_hint, fill=(*MUTED, 255), anchor="lm")
            d.text(self.s(bx0, y + 20), self._fit(mon["top"], self.f_hint, bx1 - bx0), font=self.f_hint,
                   fill=ink, anchor="lm")

    def _column_height(self, active, opened):
        """Height of the whole left column (big buttons, actions, moves) as drawn below."""
        rows = lambda n: (n + 1) // 2  # noqa: E731  two per row
        h = len(self.buttons) * 48 + rows(len(self.actions)) * 34
        if self.moves:
            h += 22
            if opened:
                h += 4 + sum(18 + rows(len(g["moves"])) * 28 + 2 for g in self.moves) + (24 if active else 0)
        return h

    def _actions(self, d, y, on):
        """A row of mini buttons for animated actions (walk, greet); returns the next free y."""
        x0, x1 = 12, PANEL_W - 12
        col_w, row_h = (x1 - x0 - 4) / 2, 28
        for i, (name, label) in enumerate(self.actions):
            bx = x0 + (i % 2) * (col_w + 4)
            rect = (bx, y, bx + col_w, y + row_h)
            hovered = self.hover == ("action", name)
            self._box(self._pressed("action", name, rect), PRI if on.get(name) else TINT if hovered else CARD,
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
        col_w, row_h, gap = (x1 - x0 - 4) / 2, 24, 4

        header = (x0, y, x1, y + 22)
        self._box(header, TINT if self.hover == ("moves_toggle", None) else CARD, radius=11, edge=2, shadow=2)
        d.text(self.s(x0 + 12, y + 11), f"Moves ({len(active)} on)" if active else "Moves", font=self.f_mini,
               fill=ink, anchor="lm")
        cx, cy = x1 - 14, y + 11  # open/closed chevron, drawn (fonts may lack the glyph)
        tri = (cx - 4, cy - 2, cx + 4, cy - 2, cx, cy + 3) if opened else (cx - 2, cy - 4, cx - 2, cy + 4, cx + 3, cy)
        self._poly(tri, INK)
        self.regions.append(("moves_toggle", None, header))
        if not opened:
            return
        y += 22 + gap

        for group in self.moves:
            # Group name on its own small ink tag, so it reads on any wallpaper.
            name = group["name"].upper()
            tw = self.f_mini.getlength(name) / self.px
            self._box((x0, y, x0 + tw + 14, y + 15), INK, radius=7, edge=0, shadow=0)
            d.text(self.s(x0 + 7, y + 7.5), name, font=self.f_mini, fill=(*SOFT, 255), anchor="lm")
            self.regions.append(("tag", None, (x0, y, x0 + tw + 14, y + 15)))
            y += 18
            for i, (exp, label) in enumerate(group["moves"]):
                bx = x0 + (i % 2) * (col_w + 4)
                rect = (bx, y, bx + col_w, y + row_h)
                on = exp in active
                hovered = self.hover == ("move", exp)
                self._box(self._pressed("move", exp, rect), PRI if on else TINT if hovered else CARD,
                          radius=8, edge=2, shadow=2)
                d.text(self.s((rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2), label, font=self.f_mini,
                       fill=ink, anchor="mm")
                self.regions.append(("move", exp, rect))
                if i % 2 or i == len(group["moves"]) - 1:
                    y += row_h + gap
            y += 2

        if active:  # one click to undo them all
            rect = (x0, y, x1, y + row_h)
            self._box(rect, TINT if self.hover == ("move", None) else CARD, radius=8, edge=2, shadow=2)
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
            self._circle(cx, cy, HANDLE_R, PRI if hovered else CARD, shadow=2)
            if name in ("left", "right"):  # double-headed horizontal arrow
                d.line(self.s(cx - a, cy, cx + a, cy), fill=ink, width=lw)
                d.line(self.s(cx - a + 4, cy - 4, cx - a, cy, cx - a + 4, cy + 4), fill=ink, width=lw)
                d.line(self.s(cx + a - 4, cy - 4, cx + a, cy, cx + a - 4, cy + 4), fill=ink, width=lw)
            else:  # double-headed vertical arrow
                d.line(self.s(cx, cy - a, cx, cy + a), fill=ink, width=lw)
                d.line(self.s(cx - 4, cy - a + 4, cx, cy - a, cx + 4, cy - a + 4), fill=ink, width=lw)
                d.line(self.s(cx - 4, cy + a - 4, cx, cy + a, cx + 4, cy + a - 4), fill=ink, width=lw)

    def _footer(self, d, text):
        tw = self.f_hint.getlength(text) / self.px
        x0, y1 = 12, self.h - 8  # bottom of the button column, clear of the bottom arrow
        rect = (x0, y1 - 22, x0 + tw + 24, y1)
        self._box(rect, radius=11, edge=2, shadow=2)
        d.text(self.s(x0 + 12, y1 - 11), text, font=self.f_hint, fill=(*INK, 255), anchor="lm")
        self.regions.append(("footer", None, rect))

    def _wrap(self, text, font, width):
        lines, line = [], ""
        for word in text.split(" "):
            trial = f"{line} {word}".strip()
            if font.getlength(trial) <= width * self.px or not line:
                line = trial
            else:
                lines.append(line)
                line = word
        lines.append(line)
        # Hard-break single words longer than the line.
        out = []
        for ln in lines:
            while font.getlength(ln) > width * self.px and len(ln) > 1:
                cut = len(ln)
                while cut > 1 and font.getlength(ln[:cut]) > width * self.px:
                    cut -= 1
                out.append(ln[:cut])
                ln = ln[cut:]
            out.append(ln)
        return out

    def _card(self, d, pendings, draft):
        pad, line_h, title_h, input_h, tail = 14, 21, 28, 30, 12
        x0 = self.left + 16
        x1 = self.w - 16
        text_x = x0 + pad + 24
        text_w = x1 - pad - text_x
        head = self.head_y if self.head_y is not None else NOTES_H
        max_h = max(NOTES_H, head) - TOP_BAR - 4  # all the room above her head, below the top strip

        # Fit as many items as the space allows, keep the input row always visible.
        rows, used, hidden = [], title_h + input_h + 2 * pad, 0
        for i, item in enumerate(pendings.items):
            lines = self._wrap(item["text"], self.f_item, text_w)
            h = len(lines) * line_h + 4
            if used + h + (line_h if i < len(pendings.items) - 1 else 0) > max_h:
                hidden = len(pendings.items) - i
                used += line_h
                break
            rows.append((i, item, lines, h))
            used += h

        bottom = max(used + TOP_BAR, head - tail)  # the bubble's tail points at the top of her head
        top = bottom - used
        self.card_top = top
        cx = self.left + self.model_w / 2
        self._panel((x0, top, x1, bottom), cx, tail)
        self.regions.append(("card", None, (x0, top, x1, bottom + tail)))

        y = top + pad
        today = datetime.date.today().strftime("%a %d %b")
        title, hint = f"Pendings · {today}", "click: done · right-click: delete"
        d.text(self.s(x0 + pad, y), title, font=self.f_title, fill=(*ACCENT, 255))
        if (self.f_title.getlength(title) + self.f_hint.getlength(hint)) / self.px + 16 < x1 - x0 - 2 * pad:
            d.text(self.s(x1 - pad, y + 3), hint, font=self.f_hint, fill=(*MUTED, 255), anchor="ra")
        y += title_h

        for index, item, lines, h in rows:
            if self.hover == ("item", index):
                self._box((x0 + 6, y - 2, x1 - 6, y + h - 2), TINT, radius=6, edge=0, shadow=0)
            self._checkbox(x0 + pad, y + 2, 15, item["done"])
            color = (*MUTED, 255) if item["done"] else (*INK, 255)
            for n, ln in enumerate(lines):
                ty = y + n * line_h
                d.text(self.s(text_x, ty), ln, font=self.f_item, fill=color)
                if item["done"]:
                    mid = ty + line_h / 2
                    d.line(self.s(text_x, mid, text_x + self.f_item.getlength(ln) / self.px, mid), fill=color,
                           width=max(1, round(self.px)))
            self.regions.append(("item", index, (x0, y - 2, x1, y + h - 2)))
            y += h

        if hidden:
            d.text(self.s(text_x, y), f"+{hidden} more", font=self.f_hint, fill=(*MUTED, 255))
            y += line_h

        # Input row: the text being typed, clipped from the left so the caret stays visible.
        iy = bottom - pad - input_h + 4
        self._box((x0 + pad, iy, x1 - pad, iy + input_h - 4), radius=8, edge=2, shadow=2)
        shown = draft
        limit = (x1 - pad - 14 - (x0 + pad + 10)) * self.px
        while shown and self.f_item.getlength(shown) > limit:
            shown = shown[1:]
        tx, ty = x0 + pad + 10, iy + (input_h - 4) / 2
        if shown:
            d.text(self.s(tx, ty), shown, font=self.f_item, fill=(*INK, 255), anchor="lm")
        else:
            hint = "Type a pending, Enter to add"
            for candidate in (hint, "Type a pending…", "Type…"):  # shortest that fits narrow cards
                if self.f_item.getlength(candidate) <= limit - 4 * self.px:
                    hint = candidate
                    break
            d.text(self.s(tx + 4, ty), hint, font=self.f_item, fill=(*MUTED, 255), anchor="lm")
        caret = tx + self.f_item.getlength(shown) / self.px + 1
        self.caret = (caret, ty)
        d.line(self.s(caret, ty - 9, caret, ty + 9), fill=(*INK, 255), width=max(1, round(2 * self.px)))
