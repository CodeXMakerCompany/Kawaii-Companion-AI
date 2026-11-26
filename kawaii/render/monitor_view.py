"""The system monitor: the CPU/GPU/RAM pill at the top right and the panel it opens, painted into their own small layer."""

from PIL import Image, ImageDraw

from kawaii.render.painter import CARD, INK, PRI, MUTED, TINT, TRACK, ALERT


def rects(p, mon):
    """Pill and (when open) panel rectangles. Fixed sizes, so changing numbers never
    move anything or need the main layer repainted."""
    w = p.f_hint.getlength("CPU 100%   GPU 100%   RAM 100%") / p.px + 40
    x1, y0 = p.w - 10, 8
    pill = (x1 - w, y0, x1, y0 + 24)
    if not mon["open"]:
        return pill, None
    pw = min(270, p.w - 20)
    ph = 12 + len(mon["rows"]) * 24 + (32 if mon.get("top") else 0) + 10
    return pill, (x1 - pw, y0 + 30, x1, y0 + 30 + ph)


def render(p, mon):
    """Paint just the monitor into a small image: (premultiplied bytes, (x, y, w, h))."""
    pill, panel = rects(p, mon)
    box = (min(pill[0], panel[0]) if panel else pill[0], pill[1], pill[2] + 4, (panel[3] if panel else pill[3]) + 5)
    w, h = round((box[2] - box[0]) * p.px), round((box[3] - box[1]) * p.px)  # with the shadows
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    regions, p.origin, main = p.regions, (box[0], box[1]), p.image
    p.image = img
    try:
        draw(p, ImageDraw.Draw(img), mon)
    finally:
        p.regions, p.origin, p.image = regions, (0, 0), main
    return img.convert("RGBa").tobytes(), (box[0], box[1], w, h)


def draw(p, d, mon):
    """Top-right system pill (CPU/GPU/RAM + status dot); click for the detail panel."""
    ink = (*INK, 255)
    level_color = {"ok": (60, 180, 100), "warn": (215, 145, 20), "alarm": ALERT}  # readable on white
    chips = "   ".join(f"{k} {v}" for k, v in mon["pill"])
    rect, panel = rects(p, mon)
    y0 = rect[1]
    p.box(rect, TINT if p.hover == ("monitor_toggle", None) else CARD, radius=12, edge=2, shadow=2.5)
    p.circle(rect[0] + 14, y0 + 12, 4.5, level_color[mon["level"]], edge=1.5)
    d.text(p.s(rect[0] + 26, y0 + 12), chips, font=p.f_hint, fill=ink, anchor="lm")
    if not panel:
        return
    rows = mon["rows"]
    p.box(panel, radius=12, edge=2.5, shadow=4)
    y = panel[1] + 10
    bx0, bx1 = panel[0] + 12, panel[2] - 12
    for label, value, frac, level in rows:
        d.text(p.s(bx0, y + 7), label, font=p.f_hint, fill=(*MUTED, 255), anchor="lm")
        d.text(p.s(bx1, y + 7), value, font=p.f_hint, fill=(*level_color[level], 255) if level != "ok"
               else ink, anchor="rm")
        if frac is not None:  # usage bar
            p.box((bx0, y + 15, bx1, y + 20), TRACK, radius=2.5, edge=0, shadow=0)
            fx = bx0 + (bx1 - bx0) * max(0.0, min(1.0, frac))
            if fx > bx0 + 5:
                p.box((bx0, y + 15, fx, y + 20), level_color[level] if level != "ok" else PRI,
                          radius=2.5, edge=0, shadow=0)
        y += 24
    if mon.get("top"):
        d.text(p.s(bx0, y + 6), "TOP PROCESS", font=p.f_hint, fill=(*MUTED, 255), anchor="lm")
        d.text(p.s(bx0, y + 20), p.fit(mon["top"], p.f_hint, bx1 - bx0), font=p.f_hint,
               fill=ink, anchor="lm")
