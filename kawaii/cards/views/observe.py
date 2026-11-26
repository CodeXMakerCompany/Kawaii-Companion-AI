"""How the Observability card is drawn: draw(painter, ImageDraw, the card's payload)."""

from kawaii.render.painter import CARD, INK, PRI, ACCENT, MUTED, TINT, TRACK, ALERT, GOOD, TOP_BAR

FOOTER = "Esc  ·  close Observability"


def draw(p, d, ob):
    """Observability: a title and a URL, Enter adds them; every 20 minutes each one gets a
    GET, a green light when it answers, red when it is not found or off."""
    ink, muted = (*INK, 255), (*MUTED, 255)
    pad, x0, x1 = 12, p.left + 16, p.w - 16
    width = x1 - x0 - 2 * pad
    eps = ob["endpoints"]
    title_h, input_h, row_h, buttons_h = 28, 30 * 2, 34, 34
    fixed = pad + title_h + input_h + 8 + buttons_h + 18 + pad
    max_h = p.h - TOP_BAR - 50
    skip = max(0, min(ob.get("skip", 0), len(eps) - 1)) if eps else 0
    p.obs_rows = len(eps)
    fit = max(1, int((max_h - fixed - (16 if skip else 0) - 16) // row_h))
    shown = list(enumerate(eps))[skip:skip + fit]
    below = len(eps) - skip - len(shown)
    used = fixed + max(1, len(shown)) * row_h + (16 if skip else 0) + (16 if below else 0)
    top, bottom, tail = p.bubble_box(used)
    p.panel((x0, top, x1, bottom), p.left + p.model_w / 2 if tail else None)
    p.regions.append(("obs_card", None, (x0, top, x1, bottom + (12 if tail else 0))))
    p.card_top, p.card_bottom = top, bottom

    y = top + pad
    n = len(eps)
    d.text(p.s(x0 + pad, y + 10), f"Observability · {n} endpoint{'s' * (n != 1)}", font=p.f_title,
           fill=(*ACCENT, 255), anchor="lm")
    note = "checking…" if ob.get("busy") else f"checked {ob['checked']}" if ob.get("checked") else "every 20 min"
    d.text(p.s(x1 - pad, y + 10), note, font=p.f_hint, fill=muted, anchor="rm")
    y += title_h

    label_w = 40
    for key, label, text, hint in (("title", "Title", ob["title"], "A name for it · Tab: next field"),
                                   ("url", "URL", ob["draft"], "Type or paste a URL · Enter adds")):
        focused = ob["focus"] == key
        d.text(p.s(x0 + pad, y + 13), label, font=p.f_day_bold, fill=ink if focused else muted, anchor="lm")
        field = (x0 + pad + label_w, y, x1 - pad, y + 26)
        p.box(field, TINT if focused else CARD, radius=8, edge=2.5 if focused else 1.5, shadow=2 if focused else 0)
        p.regions.append(("obs_title_in" if key == "title" else "obs_input", None, field))
        tx, cy = field[0] + 10, (field[1] + field[3]) / 2
        room = field[2] - field[0] - 24
        if text:
            shown_text = text
            while shown_text and p.f_day.getlength(shown_text) > room * p.px:
                shown_text = shown_text[1:]  # the end stays in view, where the caret is
            d.text(p.s(tx, cy), shown_text, font=p.f_day, fill=ink, anchor="lm")
            caret = tx + p.f_day.getlength(shown_text) / p.px + 1
        else:
            d.text(p.s(tx, cy), p.fit(hint, p.f_hint, room), font=p.f_hint, fill=muted, anchor="lm")
            caret = tx
        if focused:
            p.caret = (caret, cy)
            d.line(p.s(caret, cy - 7, caret, cy + 7), fill=ink, width=max(1, round(2 * p.px)))
        y += 30
    y += 4

    if skip:
        d.text(p.s(x0 + pad, y + 8), f"{skip} more above · scroll up", font=p.f_hint, fill=muted,
               anchor="lm")
        y += 16
    if not eps:
        d.text(p.s(x0 + pad, y + row_h / 2), "Nothing watched yet", font=p.f_hint, fill=muted, anchor="lm")
        y += row_h
    for i, e in shown:
        rect = (x0 + 6, y, x1 - 6, y + row_h - 2)
        if p.hover == ("obs_row", i):
            p.box(rect, TINT, radius=8, edge=0, shadow=0)
        light = GOOD if e.get("ok") else ALERT if e.get("ok") is False else TRACK
        p.circle(x0 + pad + 6, y + row_h / 2 - 1, 6, light, edge=1.5)
        status = e.get("status") or "waiting"
        sw = p.f_hint.getlength(status) / p.px
        d.text(p.s(x1 - pad, y + row_h / 2 - 1), status, font=p.f_hint,
               fill=(*(ALERT if e.get("ok") is False else MUTED), 255), anchor="rm")
        url = e["url"].split("://", 1)[-1]
        title = e.get("title") or url
        d.text(p.s(x0 + pad + 18, y + 10), p.fit(title, p.f_day_bold, width - 26 - sw),
               font=p.f_day_bold, fill=ink, anchor="lm")
        d.text(p.s(x0 + pad + 18, y + 24), p.fit(url, p.f_hint, width - 26 - sw),
               font=p.f_hint, fill=muted, anchor="lm")
        p.regions.append(("obs_row", i, rect))
        y += row_h
    if below:
        d.text(p.s(x0 + pad, y + 8), f"{below} more below · scroll down", font=p.f_hint, fill=muted,
               anchor="lm")
        y += 16

    y = bottom - pad - 18 - buttons_h + 6
    bx = x0 + pad
    for kind, label, fill in (("obs_add", "Add", PRI), ("obs_paste", "Paste", CARD), ("obs_check", "Check now", CARD),
                              ("obs_done", "Done", CARD)):
        w = p.f_mini.getlength(label) / p.px + 24
        rect = (bx, y, bx + w, y + 26)
        hovered = p.hover == (kind, None)
        p.box(p.pressed(kind, None, rect), TINT if hovered else fill, radius=9, edge=2, shadow=2.5)
        d.text(p.s(bx + w / 2, y + 13), label, font=p.f_mini, fill=ink, anchor="mm")
        p.regions.append((kind, None, rect))
        bx += w + 6
    note = ob.get("status") or "Click an endpoint to copy its URL · right-click removes it"
    d.text(p.s(x0 + pad, bottom - pad - 6), p.fit(note, p.f_hint, width), font=p.f_hint,
           fill=(*(ALERT if "install" in note.lower() else MUTED), 255), anchor="lm")
