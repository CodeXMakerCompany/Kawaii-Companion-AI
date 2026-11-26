"""The overlay's look and its drawing primitives, shared by the side column, the bubbles
and every card's view.

The look is Sakuga VFX's (github.com/finktheartist/sakuga-vfx, MIT): white cards with an
inked edge and a hard lavender shadow, bold italic labels, violet when switched on. The
click effects in fx.py use the same palette.

Coordinates passed in are window coordinates; s() turns them into image pixels.
"""

import datetime
import functools
import subprocess

from PIL import Image, ImageDraw, ImageFont

PANEL_W = 150  # left button column
NOTES_H = 230  # space above her head for the card
HANDLE_R = 14  # resize arrow radius
TOP_BAR = 38  # strip kept free at the top for the system monitor pill
BUTTON_H, BUTTON_STEP = 32, 40  # the big side buttons: height, and from one to the next

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
GOOD = (46, 189, 107)  # endpoints that answer


def ago(iso):
    """'5m ago' for an ISO 8601 UTC time (as GitHub gives them)."""
    try:
        then = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return ""
    s = max(0, (datetime.datetime.now(datetime.timezone.utc) - then).total_seconds())
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60)):
        if s >= size:
            return f"{int(s // size)}{unit} ago"
    return "just now"


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


class Painter:
    """Paints into one Pillow image and records what was drawn where (regions), so the
    overlay can answer hit tests in window coordinates."""

    def __init__(self, px):
        self.px = px
        self.origin = (0, 0)  # drawing origin (window coords) of the image being painted
        self.head_y = None  # top of her head in window coords, once measured
        self.f_button = load_font("sans:bold:italic", round(15 * px))
        self.f_mini = load_font("sans:bold:italic", round(11 * px))  # mini buttons
        self.f_title = load_font("sans:bold:italic", round(15 * px))
        self.f_item = load_font("sans", round(15 * px))
        self.f_hint = load_font("sans", round(11 * px))
        self.f_day = load_font("sans", round(13 * px))
        self.f_day_bold = load_font("sans:bold", round(13 * px))
        self.f_mono = load_font("monospace", round(12 * px))  # decoded output
        self.hover = None
        self.regions = []  # (kind, name, rect) of everything clickable, in drawing order
        self.squash = {}  # (kind, name) -> (x scale, y scale) of buttons being pressed (fx.Press)
        self.flash = None  # (kind, name) of a button drawn inverted for an instant: the impact frame
        self.caret = None  # (x, y) of the text caret in the open card, for typing effects
        self.card_top = self.card_bottom = None  # the open card's extent, once drawn
        self.image = None  # the image being painted
        # Rows as last drawn by the scrolling cards (their cards clamp the wheel with these).
        self.pr_rows = self.dec_rows = self.pk_rows = self.obs_rows = 0
        self.rules_rows = self.rules_skip = 0

    def begin_frame(self, image):
        """Start painting a fresh layer: nothing drawn, nothing clickable yet."""
        self.image = image
        self.regions = []
        self.caret = None
        self.card_top = self.card_bottom = None

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

    def pressed(self, kind, name, rect):
        """rect squashed around its centre while its button springs back from a press."""
        s = self.squash.get((kind, name))
        if not s:
            return rect
        cx, cy = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
        hw, hh = (rect[2] - rect[0]) / 2 * s[0], (rect[3] - rect[1]) / 2 * s[1]
        return cx - hw, cy - hh, cx + hw, cy + hh

    def paste(self, sprite, x, y):
        """Blend a sprite onto the image being painted, its top-left at image pixel (x, y)."""
        cx, cy = max(0, -x), max(0, -y)  # cropped where it hangs off the top or left edge
        if cx or cy:
            if cx >= sprite.width or cy >= sprite.height:
                return
            sprite = sprite.crop((cx, cy, sprite.width, sprite.height))
        self.image.alpha_composite(sprite, (x + cx, y + cy))

    def box(self, rect, fill=CARD, radius=12, edge=2.5, shadow=4):
        """A Sakuga box at rect (window coords): inked edge, hard shadow down and right."""
        x0, y0, x1, y1 = self.s(*rect)
        if x1 <= x0 or y1 <= y0:
            return
        sh = (round(shadow * self.px), round(shadow * 7 / 6 * self.px))
        self.paste(box_sprite(x1 - x0, y1 - y0, round(radius * self.px), tuple(fill[:3]), edge * self.px, sh),
                    x0, y0)

    def circle(self, cx, cy, r, fill=CARD, edge=2.0, shadow=0):
        self.box((cx - r, cy - r, cx + r, cy + r), fill, radius=r, edge=edge, shadow=shadow)

    def poly(self, points, fill):
        """An antialiased polygon from window-coord x, y pairs."""
        pts = self.s(*points)
        xs, ys = pts[0::2], pts[1::2]
        x0, y0 = min(xs), min(ys)
        self.paste(poly_sprite(tuple((x - x0, y - y0) for x, y in zip(xs, ys)), (*fill[:3], 255)), x0, y0)

    def panel(self, rect, tail_x=None, tail=12):
        """A white card with an inked edge; tail_x: a speech-bubble tail under it there."""
        self.box(rect, radius=14, edge=2.5, shadow=5)
        if tail_x is not None:
            bottom = rect[3]
            self.poly((tail_x - 12, bottom - 2.5, tail_x + 12, bottom - 2.5, tail_x, bottom + tail + 2), INK)
            self.poly((tail_x - 8, bottom - 3, tail_x + 8, bottom - 3, tail_x, bottom + tail - 2.5), CARD)

    def checkbox(self, bx, by, size, done):
        """A Sakuga checkbox: a white inked box, an ink tick when done."""
        self.box((bx, by, bx + size, by + size), radius=4, edge=1.8, shadow=0)
        if done:
            k = size / 15
            self.tick(bx + 3.5 * k, by + 8 * k, bx + 6.5 * k, by + 11 * k, bx + 12 * k, by + 4.5 * k)

    def tick(self, *pts):
        ImageDraw.Draw(self.image).line(self.s(*pts), fill=(*INK, 255), width=max(1, round(2.4 * self.px)),
                                       joint="curve")

    def hit(self, x, y):
        for kind, index, (x0, y0, x1, y1) in reversed(self.regions):
            if x0 <= x < x1 and y0 <= y < y1:
                return kind, index
        return None

    def fit(self, text, font, width):
        """text, shortened with an ellipsis to fit `width` (window units)."""
        if font.getlength(text) <= width * self.px:
            return text
        while text and font.getlength(text + "…") > width * self.px:
            text = text[:-1]
        return text + "…"

    def wrap(self, text, font, width):
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

    def wrap_chars(self, text, font, width):
        """Lines of text broken anywhere to fit `width` (for code and data, where words are long)."""
        out = []
        limit = width * self.px
        for line in text.split("\n"):
            line = line.replace("\t", "    ")
            while line and font.getlength(line) > limit:
                n = max(1, int(len(line) * limit / font.getlength(line)))
                while n > 1 and font.getlength(line[:n]) > limit:
                    n -= 1
                out.append(line[:n])
                line = line[n:]
            out.append(line)
        return out

    def bubble_box(self, used, above=None):
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

    def footer(self, d, text):
        tw = self.f_hint.getlength(text) / self.px
        x0, y1 = 12, self.h - 8  # bottom of the button column, clear of the bottom arrow
        rect = (x0, y1 - 22, x0 + tw + 24, y1)
        self.box(rect, radius=11, edge=2, shadow=2)
        d.text(self.s(x0 + 12, y1 - 11), text, font=self.f_hint, fill=(*INK, 255), anchor="lm")
        self.regions.append(("footer", None, rect))
