"""The system monitor: the CPU/GPU/RAM pill at the top right and the panel it opens, under
them the Focus switch with its countdown and dropdown, then the customer clocks, painted
into their own small layer (their numbers change every second or two; the main layer only repaints for clicks)."""

from PIL import Image, ImageDraw

from kawaii.render.painter import ALERT, CARD, INK, MUTED, PINK, PRI, TINT, TRACK


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


def focus_rects(p, mon, focus):
    """The Focus switch under the pill (or its open panel), the dropdown under the switch
    while focus is on and it is open: (switch, timer/chevron part or None, dropdown or None)."""
    pill, panel = rects(p, mon or {"open": False})
    x0, x1, y = pill[0], pill[2], (panel or pill)[3] + 6
    switch = (x0, y, x1, y + 24)
    if not focus["on"]:
        return switch, None, None
    chevron = (x1 - 46, y, x1, y + 24)
    if not focus["open"]:
        return switch, chevron, None
    pw = min(270, p.w - 20)
    ph = 10 + 18 + len(focus["rows"]) * 20 + 8 + 26 + 10
    return switch, chevron, (x1 - pw, y + 30, x1, y + 30 + ph)


CLOCK_ROW, CLOCK_HEADER, CLOCK_TOGGLE = 24, 20, 22


def _clock_groups(clocks):
    """The rows with a header before each new group (customers have none): [(header, row)]."""
    out, last = [], None
    for row in clocks["rows"]:
        header = row["group"] if row["group"] and row["group"] != last else None
        last = row["group"]
        out.append((header, row))
    return out


def clocks_rect(p, mon, focus, clocks):
    """The customer clocks card: under the Focus switch (and its dropdown when open)."""
    pill, panel = rects(p, mon or {"open": False})
    above = (panel or pill)[3]
    if focus:
        switch, _, drop = focus_rects(p, mon, focus)
        above = (drop or switch)[3]
    groups = _clock_groups(clocks)
    h = 8 + len(groups) * CLOCK_ROW + sum(CLOCK_HEADER for header, _ in groups if header) + 4
    if clocks["expanded"] or clocks["hidden"]:
        h += CLOCK_TOGGLE
    return (pill[0], above + 6, pill[2], above + 6 + h)


def _clocks_toggle(rect):
    return (rect[0] + 6, rect[3] - 4 - CLOCK_TOGGLE, rect[2] - 6, rect[3] - 4)


def regions(p, mon, focus, clocks=None):
    """Click areas for the main layer (this layer is painted separately)."""
    out = []
    if mon:
        pill, panel = rects(p, mon)
        out.append(("monitor_toggle", None, pill))
        if panel:
            out.append(("monitor_panel", None, panel))
    if focus:
        switch, chevron, drop = focus_rects(p, mon, focus)
        out.append(("focus_toggle", None, (switch[0], switch[1], chevron[0], switch[3]) if chevron else switch))
        if chevron:
            out.append(("focus_open", None, chevron))
        if drop:
            out.append(("focus_panel", None, drop))
            for kind, rect in _focus_buttons(drop):
                out.append((kind, None, rect))
    if clocks:
        rect = clocks_rect(p, mon, focus, clocks)
        out.append(("clocks", None, rect))
        if clocks["expanded"] or clocks["hidden"]:
            out.append(("clocks_more", None, _clocks_toggle(rect)))
    return out


def _focus_buttons(drop):
    y = drop[3] - 10 - 26
    return [("focus_plus", (drop[0] + 12, y, drop[0] + 88, y + 26)),
            ("focus_end", (drop[0] + 96, y, drop[0] + 190, y + 26))]


def render(p, mon, focus=None, clocks=None):
    """Paint just this layer into a small image: (premultiplied bytes, (x, y, w, h))."""
    pill, panel = rects(p, mon or {"open": False})
    boxes = ([pill] + ([panel] if panel else [])) if mon else []
    if focus:
        boxes += [r for r in focus_rects(p, mon, focus) if r]
    if clocks:
        boxes.append(clocks_rect(p, mon, focus, clocks))
    box = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes) + 4,
           max(b[3] for b in boxes) + 5)
    w, h = round((box[2] - box[0]) * p.px), round((box[3] - box[1]) * p.px)  # with the shadows
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    regions, p.origin, main = p.regions, (box[0], box[1]), p.image
    p.image = img
    try:
        d = ImageDraw.Draw(img)
        if mon:
            draw(p, d, mon)
        if focus:
            draw_focus(p, d, mon, focus)
        if clocks:
            draw_clocks(p, d, mon, focus, clocks)
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


def draw_focus(p, d, mon, focus):
    """The Focus switch (with the countdown while on) and, opened from its chevron, the
    dropdown counting what is waiting, with +5 min and End focus."""
    ink, muted = (*INK, 255), (*MUTED, 255)
    switch, chevron, drop = focus_rects(p, mon, focus)
    on = focus["on"]
    hovered = p.hover in (("focus_toggle", None), ("focus_open", None))
    p.box(switch, PRI if on and not hovered else TINT if hovered else CARD, radius=12, edge=2, shadow=2.5)
    x0, y0 = switch[0], switch[1]
    track = (x0 + 10, y0 + 6, x0 + 34, y0 + 18)  # the switch itself
    p.box(track, INK if on else TRACK, radius=6, edge=1.5, shadow=0)
    p.circle(track[2] - 6 if on else track[0] + 6, y0 + 12, 5, CARD, edge=1.5)
    d.text(p.s(x0 + 42, y0 + 12), "Focus" + (f"  ·  {focus['label']}" if on else ""), font=p.f_hint,
           fill=ink, anchor="lm")
    if chevron:
        cx, cy = chevron[0] + 16, y0 + 12
        tri = (cx - 4, cy - 2, cx + 4, cy - 2, cx, cy + 3) if not focus["open"] else (cx - 4, cy + 2, cx + 4, cy + 2,
                                                                                      cx, cy - 3)
        p.poly(tri, INK)
        if focus["total"]:
            p.circle(chevron[0] + 33, cy, 9, PINK, edge=1.5)
            d.text(p.s(chevron[0] + 33, cy), str(focus["total"]), font=p.f_mini, anchor="mm",
                   fill=(255, 255, 255, 255))
    if not drop:
        return
    p.box(drop, radius=12, edge=2.5, shadow=4)
    bx0, bx1 = drop[0] + 12, drop[2] - 12
    y = drop[1] + 10
    d.text(p.s(bx0, y + 7), "WHILE YOU FOCUS", font=p.f_hint, fill=muted, anchor="lm")
    y += 18
    for label, count in focus["rows"]:
        d.text(p.s(bx0, y + 9), label, font=p.f_hint, fill=ink if count else muted, anchor="lm")
        d.text(p.s(bx1, y + 9), str(count), font=p.f_day_bold if count else p.f_hint,
               fill=ink if count else muted, anchor="rm")
        y += 20
    for kind, rect in _focus_buttons(drop):
        label = "+5 min" if kind == "focus_plus" else "End focus"
        p.box(p.pressed(kind, None, rect), TINT if p.hover == (kind, None) else CARD, radius=9, edge=2, shadow=2.5)
        d.text(p.s((rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2), label, font=p.f_mini, fill=ink, anchor="mm")


SUN = (255, 184, 0)


def draw_clocks(p, d, mon, focus, clocks):
    """One row per zone: a sun or moon, the name (with its city for cloud zones), how far
    ahead of you, and the time in bold; people's rows dim outside their working hours.
    A small header starts each group, and the toggle at the bottom folds the cloud zones."""
    rect = clocks_rect(p, mon, focus, clocks)
    p.box(rect, radius=12, edge=2, shadow=2.5)
    x0, x1 = rect[0] + 12, rect[2] - 12
    muted = (*MUTED, 255)
    y = rect[1] + 6
    for header, c in _clock_groups(clocks):
        if header:
            d.line(p.s(x0, y + 4, x1, y + 4), fill=(*TRACK, 255), width=max(1, round(p.px)))
            d.text(p.s(x0, y + 12), header.upper(), font=p.f_hint, fill=muted, anchor="lm")
            y += CLOCK_HEADER
        cy = y + 12
        if c["day"]:
            p.circle(x0 + 5, cy, 5, SUN, edge=1.5)
        else:  # a crescent: a lavender disc with a white one over most of it
            p.circle(x0 + 5, cy, 5.5, PRI, edge=1.5)
            p.circle(x0 + 7.5, cy - 2, 4.2, CARD, edge=0)
        colour = (*(MUTED if c["working"] is False else INK), 255)
        d.text(p.s(x0 + 18, cy), c["name"], font=p.f_day, fill=colour, anchor="lm")
        nx = x0 + 18 + p.f_day.getlength(c["name"]) / p.px + 6
        room = x1 - p.f_day_bold.getlength(c["time"]) / p.px - 8 - nx
        for extra in (t for t in (c.get("place"), c["diff"]) if t):  # each only when it fits whole
            w = p.f_hint.getlength(extra) / p.px
            if w > room:
                break
            d.text(p.s(nx, cy + 1), extra, font=p.f_hint, fill=muted, anchor="lm")
            nx, room = nx + w + 6, room - w - 6
        d.text(p.s(x1, cy), c["time"], font=p.f_day_bold, fill=colour, anchor="rm")
        y += CLOCK_ROW
    if clocks["expanded"] or clocks["hidden"]:
        t = _clocks_toggle(rect)
        if p.hover == ("clocks_more", None):
            p.box(t, TINT, radius=8, edge=0, shadow=0)
        label = "fewer zones" if clocks["expanded"] else f"{clocks['hidden']} cloud zones"
        cx, cy = (t[0] + t[2]) / 2 + 7, (t[1] + t[3]) / 2
        d.text(p.s(cx, cy), label, font=p.f_hint, fill=muted, anchor="mm")
        ax = cx - p.f_hint.getlength(label) / p.px / 2 - 10  # the arrow, drawn (fonts may lack the glyph)
        p.poly((ax - 4, cy + 2, ax + 4, cy + 2, ax, cy - 3) if clocks["expanded"] else
               (ax - 4, cy - 2, ax + 4, cy - 2, ax, cy + 3), MUTED)
