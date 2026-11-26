"""How the Pendings card is drawn: draw(painter, ImageDraw, the card's payload)."""

import datetime

from kawaii.render.painter import INK, ACCENT, MUTED, TINT, NOTES_H, TOP_BAR

FOOTER = "Esc  ·  close the list"


def draw(p, d, card):
    """The list above her head: a row per item (click toggles, right-click deletes), then the input line."""
    pendings, draft = card["pendings"], card["draft"]
    pad, line_h, title_h, input_h, tail = 14, 21, 28, 30, 12
    x0 = p.left + 16
    x1 = p.w - 16
    text_x = x0 + pad + 24
    text_w = x1 - pad - text_x
    head = p.head_y if p.head_y is not None else NOTES_H
    max_h = max(NOTES_H, head) - TOP_BAR - 4  # all the room above her head, below the top strip

    # Fit as many items as the space allows, keep the input row always visible.
    rows, used, hidden = [], title_h + input_h + 2 * pad, 0
    for i, item in enumerate(pendings.items):
        lines = p.wrap(item["text"], p.f_item, text_w)
        h = len(lines) * line_h + 4
        if used + h + (line_h if i < len(pendings.items) - 1 else 0) > max_h:
            hidden = len(pendings.items) - i
            used += line_h
            break
        rows.append((i, item, lines, h))
        used += h

    bottom = max(used + TOP_BAR, head - tail)  # the bubble's tail points at the top of her head
    top = bottom - used
    p.card_top, p.card_bottom = top, bottom
    cx = p.left + p.model_w / 2
    p.panel((x0, top, x1, bottom), cx, tail)
    p.regions.append(("card", None, (x0, top, x1, bottom + tail)))

    y = top + pad
    today = datetime.date.today().strftime("%a %d %b")
    title, hint = f"Pendings · {today}", "click: done · right-click: delete"
    d.text(p.s(x0 + pad, y), title, font=p.f_title, fill=(*ACCENT, 255))
    if (p.f_title.getlength(title) + p.f_hint.getlength(hint)) / p.px + 16 < x1 - x0 - 2 * pad:
        d.text(p.s(x1 - pad, y + 3), hint, font=p.f_hint, fill=(*MUTED, 255), anchor="ra")
    y += title_h

    for index, item, lines, h in rows:
        if p.hover == ("item", index):
            p.box((x0 + 6, y - 2, x1 - 6, y + h - 2), TINT, radius=6, edge=0, shadow=0)
        p.checkbox(x0 + pad, y + 2, 15, item["done"])
        color = (*MUTED, 255) if item["done"] else (*INK, 255)
        for n, ln in enumerate(lines):
            ty = y + n * line_h
            d.text(p.s(text_x, ty), ln, font=p.f_item, fill=color)
            if item["done"]:
                mid = ty + line_h / 2
                d.line(p.s(text_x, mid, text_x + p.f_item.getlength(ln) / p.px, mid), fill=color,
                       width=max(1, round(p.px)))
        p.regions.append(("item", index, (x0, y - 2, x1, y + h - 2)))
        y += h

    if hidden:
        d.text(p.s(text_x, y), f"+{hidden} more", font=p.f_hint, fill=(*MUTED, 255))
        y += line_h

    # Input row: the text being typed, clipped from the left so the caret stays visible.
    iy = bottom - pad - input_h + 4
    p.box((x0 + pad, iy, x1 - pad, iy + input_h - 4), radius=8, edge=2, shadow=2)
    shown = draft
    limit = (x1 - pad - 14 - (x0 + pad + 10)) * p.px
    while shown and p.f_item.getlength(shown) > limit:
        shown = shown[1:]
    tx, ty = x0 + pad + 10, iy + (input_h - 4) / 2
    if shown:
        d.text(p.s(tx, ty), shown, font=p.f_item, fill=(*INK, 255), anchor="lm")
    else:
        hint = "Type a pending, Enter to add"
        for candidate in (hint, "Type a pending…", "Type…"):  # shortest that fits narrow cards
            if p.f_item.getlength(candidate) <= limit - 4 * p.px:
                hint = candidate
                break
        d.text(p.s(tx + 4, ty), hint, font=p.f_item, fill=(*MUTED, 255), anchor="lm")
    caret = tx + p.f_item.getlength(shown) / p.px + 1
    p.caret = (caret, ty)
    d.line(p.s(caret, ty - 9, caret, ty + 9), fill=(*INK, 255), width=max(1, round(2 * p.px)))
