"""How the Decode card is drawn: draw(painter, ImageDraw, the card's payload)."""

from kawaii.render.painter import CARD, INK, PRI, ACCENT, PINK, MUTED, TINT, TOP_BAR

FOOTER = "Esc  ·  close Decode"


def draw(p, d, dec):
    """Paste or type something, Decode shows what it is (JWT claims, a date, pretty JSON...),
    Copy puts the result on the clipboard; a stack trace can be sent for an explanation."""
    ink, muted = (*INK, 255), (*MUTED, 255)
    pad, x0, x1 = 12, p.left + 16, p.w - 16
    width = x1 - x0 - 2 * pad
    result = dec.get("result")

    # The text being decoded: its last lines, so the caret stays in view.
    draft = dec["draft"]
    lines = p.wrap_chars(draft, p.f_mono, width - 20)[-4:] if draft else []
    input_h = max(1, len(lines)) * 15 + 14

    rows = []  # (kind, height, payload): the result, scrollable
    if result:
        for heading, text in result.sections:
            rows.append(("head", 18, heading))
            rows += [("mono", 15, ln) for ln in p.wrap_chars(text, p.f_mono, width - 8)]
            rows.append(("gap", 6, None))
    if dec.get("explanation"):
        rows.append(("head", 18, "Explanation"))
        rows += [("prose", 15, ln) for ln in p.wrap(dec["explanation"], p.f_hint, width - 8)]
    p.dec_rows = len(rows)

    title_h, buttons_h = 28, 34
    fixed = pad + title_h + input_h + 8 + buttons_h + pad
    max_h = p.h - TOP_BAR - 50
    skip = max(0, min(dec.get("skip", 0), len(rows) - 1)) if rows else 0
    used, shown = fixed + (16 if skip else 0), []
    for i, row in enumerate(rows[skip:], skip):
        if used + row[1] + (16 if i < len(rows) - 1 else 0) > max_h:
            break
        shown.append(row)
        used += row[1]
    below = len(rows) - skip - len(shown)
    if below:
        used += 16
    top, bottom, tail = p.bubble_box(used)
    p.panel((x0, top, x1, bottom), p.left + p.model_w / 2 if tail else None)
    p.regions.append(("dec_card", None, (x0, top, x1, bottom + (12 if tail else 0))))
    p.card_top, p.card_bottom = top, bottom

    y = top + pad
    title = f"Decode · {result.kind}" if result else "Decode"
    d.text(p.s(x0 + pad, y + 10), p.fit(title, p.f_title, width - 120), font=p.f_title,
           fill=(*ACCENT, 255), anchor="lm")
    d.text(p.s(x1 - pad, y + 10), "Enter: decode", font=p.f_hint, fill=muted, anchor="rm")
    y += title_h

    field = (x0 + pad, y, x1 - pad, y + input_h)
    p.box(field, radius=8, edge=2, shadow=2)
    p.regions.append(("dec_input", None, field))
    tx = field[0] + 10
    if lines:
        for i, ln in enumerate(lines):
            d.text(p.s(tx, y + 7 + 15 * i + 7), ln, font=p.f_mono, fill=ink, anchor="lm")
        cy = y + 7 + 15 * (len(lines) - 1) + 7
        caret = tx + p.f_mono.getlength(lines[-1]) / p.px + 1
    else:
        d.text(p.s(tx, y + 14), p.fit("Paste or type a JWT, timestamp, JSON, stack trace…", p.f_hint,
                                             width - 24), font=p.f_hint, fill=muted, anchor="lm")
        cy, caret = y + 14, tx
    p.caret = (caret, cy)
    d.line(p.s(caret, cy - 7, caret, cy + 7), fill=ink, width=max(1, round(2 * p.px)))
    y += input_h + 8

    # Paste, Decode, Clear; Copy and Explain? once there is something to copy or explain.
    bx = x0 + pad
    buttons = [("dec_paste", "Paste", CARD), ("dec_run", "Decode", PRI), ("dec_clear", "Clear", CARD)]
    if result or dec.get("explanation"):
        buttons.append(("dec_copy", "Copy", CARD))
    if result and result.explain:
        buttons.append(("dec_explain", "Explain?", PINK))
    for kind, label, fill in buttons:
        w = p.f_mini.getlength(label) / p.px + 24
        rect = (bx, y, bx + w, y + 26)
        hovered = p.hover == (kind, None) and fill == CARD
        p.box(p.pressed(kind, None, rect), TINT if hovered else fill, radius=9, edge=2, shadow=2.5)
        d.text(p.s(bx + w / 2, y + 13), label, font=p.f_mini, fill=ink, anchor="mm")
        p.regions.append((kind, None, rect))
        bx += w + 6
    status = dec.get("status") or ("" if dec.get("clipboard") else "Paste/Copy need wl-clipboard")
    if status:
        d.text(p.s(x1 - pad, y + 13), p.fit(status, p.f_hint, x1 - pad - bx - 6), font=p.f_hint,
               fill=muted, anchor="rm")
    y += buttons_h

    if skip:
        d.text(p.s(x0 + pad, y + 8), "more above · scroll up", font=p.f_hint, fill=muted, anchor="lm")
        y += 16
    for kind, h, payload in shown:
        if kind == "head":
            d.text(p.s(x0 + pad, y + 9), payload, font=p.f_day_bold, fill=muted, anchor="lm")
            if result and result.swatch and payload == result.sections[0][0]:  # the color itself
                sw = p.f_day_bold.getlength(payload) / p.px + 10
                p.box((x0 + pad + sw, y + 2, x0 + pad + sw + 40, y + 16), result.swatch, radius=4,
                          edge=1.5, shadow=0)
        elif kind == "mono":
            d.text(p.s(x0 + pad + 4, y + 7), payload, font=p.f_mono, fill=ink, anchor="lm")
        elif kind == "prose":
            d.text(p.s(x0 + pad + 4, y + 7), payload, font=p.f_hint, fill=ink, anchor="lm")
        y += h
    if below:
        d.text(p.s(x0 + pad, y + 8), f"{below} more lines · scroll down", font=p.f_hint, fill=muted,
               anchor="lm")
