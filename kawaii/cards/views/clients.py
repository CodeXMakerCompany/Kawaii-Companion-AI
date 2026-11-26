"""How the Clients card is drawn: draw(painter, ImageDraw, the card's payload)."""

from kawaii.render.painter import ACCENT, ALERT, CARD, INK, MUTED, PRI, TINT, TOP_BAR

FOOTER = "Esc  ·  close Clients"


def draw(p, d, cl):
    """The clients (the current one ticked), a field to add one, Add and Done."""
    ink, muted = (*INK, 255), (*MUTED, 255)
    pad, x0, x1 = 12, p.left + 16, p.w - 16
    width = x1 - x0 - 2 * pad
    rows = cl["rows"]
    title_h, input_h, buttons_h, row_h = 28, 30, 34, 30
    fixed = pad + title_h + input_h + 8 + buttons_h + 18 + pad
    room = p.h - TOP_BAR - 50 - fixed - 32
    skip = max(0, min(cl.get("skip", 0), len(rows) - 1)) if rows else 0
    p.client_rows = len(rows)
    shown = list(enumerate(rows))[skip:skip + max(1, int(room // row_h))]
    below = len(rows) - skip - len(shown)
    used = fixed + len(shown) * row_h + (16 if skip else 0) + (16 if below else 0)
    top, bottom, tail = p.bubble_box(used)
    p.panel((x0, top, x1, bottom), p.left + p.model_w / 2 if tail else None)
    p.regions.append(("client_card", None, (x0, top, x1, bottom + (12 if tail else 0))))
    p.card_top, p.card_bottom = top, bottom

    y = top + pad
    note = f"{len(rows)} client{'s' * (len(rows) != 1)}"
    d.text(p.s(x0 + pad, y + 10), "Clients", font=p.f_title, fill=(*ACCENT, 255), anchor="lm")
    d.text(p.s(x1 - pad, y + 10), note, font=p.f_hint, fill=muted, anchor="rm")
    y += title_h

    label_w = p.f_day_bold.getlength("New") / p.px + 8
    d.text(p.s(x0 + pad, y + 13), "New", font=p.f_day_bold, fill=ink, anchor="lm")
    field = (x0 + pad + label_w, y, x1 - pad, y + 26)
    p.box(field, TINT, radius=8, edge=2.5, shadow=2)
    p.regions.append(("client_input", None, field))
    tx, cy = field[0] + 10, (field[1] + field[3]) / 2
    if cl["draft"]:
        text = cl["draft"]
        while text and p.f_day.getlength(text) > (field[2] - field[0] - 24) * p.px:
            text = text[1:]
        d.text(p.s(tx, cy), text, font=p.f_day, fill=ink, anchor="lm")
        caret = tx + p.f_day.getlength(text) / p.px + 1
    else:
        d.text(p.s(tx, cy), "A client's name · Enter adds it and switches to it", font=p.f_hint, fill=muted,
               anchor="lm")
        caret = tx
    p.caret = (caret, cy)
    d.line(p.s(caret, cy - 7, caret, cy + 7), fill=ink, width=max(1, round(2 * p.px)))
    y += input_h + 8

    if skip:
        d.text(p.s(x0 + pad, y + 8), f"{skip} more above · scroll up", font=p.f_hint, fill=muted, anchor="lm")
        y += 16
    for i, row in shown:
        rect = (x0 + 6, y, x1 - 6, y + row_h - 2)
        if row["current"]:
            p.box(rect, PRI, radius=8, edge=0, shadow=0)
        elif p.hover == ("client_row", i):
            p.box(rect, TINT, radius=8, edge=0, shadow=0)
        cy = y + row_h / 2 - 1
        d.text(p.s(x0 + pad, cy), p.fit(row["name"], p.f_day_bold, width - 80), font=p.f_day_bold, fill=ink,
               anchor="lm")
        d.text(p.s(x1 - pad, cy), "working on it" if row["current"] else "switch  ›", font=p.f_hint,
               fill=ink if row["current"] else muted, anchor="rm")
        p.regions.append(("client_row", i, rect))
        y += row_h
    if below:
        d.text(p.s(x0 + pad, y + 8), f"{below} more below · scroll down", font=p.f_hint, fill=muted, anchor="lm")

    y = bottom - pad - 18 - buttons_h + 6
    bx = x0 + pad
    for kind, label, fill in (("client_add", "Add", PRI), ("client_done", "Done", CARD)):
        w = p.f_mini.getlength(label) / p.px + 24
        rect = (bx, y, bx + w, y + 26)
        p.box(p.pressed(kind, None, rect), TINT if p.hover == (kind, None) else fill, radius=9, edge=2, shadow=2.5)
        d.text(p.s(bx + w / 2, y + 13), label, font=p.f_mini, fill=ink, anchor="mm")
        p.regions.append((kind, None, rect))
        bx += w + 6
    note = cl.get("status") or "Each client has its own pendings, reminders, endpoints, rules and vault"
    d.text(p.s(x0 + pad, bottom - pad - 6), p.fit(note, p.f_hint, width), font=p.f_hint,
           fill=(*(ALERT if note.startswith(("Choose", "Switch")) else MUTED), 255), anchor="lm")
