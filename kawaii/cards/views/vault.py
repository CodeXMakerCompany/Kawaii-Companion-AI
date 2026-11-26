"""How the Vault card is drawn: draw(painter, ImageDraw, the card's payload). It only ever
gets keys masked: the real ones never reach the screen layer."""

from kawaii.render.painter import ACCENT, ALERT, CARD, INK, MUTED, PRI, TINT, TOP_BAR

FOOTER = "Esc  ·  close the Vault"


def _field(p, d, x0, x1, y, label, label_w, kind, text, hint, focused, mono=False):
    """A labelled one-line field; the caret sits in the focused one."""
    ink, muted = (*INK, 255), (*MUTED, 255)
    d.text(p.s(x0, y + 13), label, font=p.f_day_bold, fill=ink, anchor="lm")
    field = (x0 + label_w, y, x1, y + 26)
    p.box(field, TINT if focused else CARD, radius=8, edge=2.5 if focused else 2, shadow=2)
    p.regions.append((kind, None, field))
    tx, cy = field[0] + 10, (field[1] + field[3]) / 2
    space = field[2] - field[0] - 24
    font = p.f_mono if mono else p.f_day
    if text:
        shown = text
        while shown and font.getlength(shown) > space * p.px:
            shown = shown[1:]  # the end stays in view, where the caret is
        d.text(p.s(tx, cy), shown, font=font, fill=ink, anchor="lm")
        caret = tx + font.getlength(shown) / p.px + 1
    else:
        d.text(p.s(tx, cy), p.fit(hint, p.f_hint, space), font=p.f_hint, fill=muted, anchor="lm")
        caret = tx
    if focused:
        p.caret = (caret, cy)
        d.line(p.s(caret, cy - 7, caret, cy + 7), fill=ink, width=max(1, round(2 * p.px)))


def draw(p, d, vt):
    """Vault: the reasons (type one, Enter opens it, new or not), and inside one, its keys
    masked, with a Name and a Key field to add another (Temp 24h: it deletes itself)."""
    ink, muted = (*INK, 255), (*MUTED, 255)
    pad, x0, x1 = 12, p.left + 16, p.w - 16
    width = x1 - x0 - 2 * pad
    inside = vt["reason"] is not None
    rows = vt["keys"] if inside else vt["reasons"]
    title_h, input_h, buttons_h, row_h = 28, 30, 34, 30
    fixed = pad + title_h + input_h * (2 if inside else 1) + 8 + buttons_h + 18 + pad
    max_h = p.h - TOP_BAR - 50
    skip = max(0, min(vt.get("skip", 0), len(rows) - 1)) if rows else 0
    p.vault_rows = len(rows)
    room = max_h - fixed - (16 if skip else 0) - 16
    fit = max(1, int(room // row_h))
    shown = list(enumerate(rows))[skip:skip + fit]
    below = len(rows) - skip - len(shown)
    used = fixed + max(34, len(shown) * row_h) + (16 if skip else 0) + (16 if below else 0)
    top, bottom, tail = p.bubble_box(used)
    p.panel((x0, top, x1, bottom), p.left + p.model_w / 2 if tail else None)
    p.regions.append(("vault_card", None, (x0, top, x1, bottom + (12 if tail else 0))))
    p.card_top, p.card_bottom = top, bottom

    y = top + pad
    if inside:
        n = len(rows)
        title, note = vt["reasons"][vt["reason"]]["name"], f"{n} key{'s' * (n != 1)}"
    else:
        n = len(rows)
        title, note = "Vault", f"{n} reason{'s' * (n != 1)} · {vt['count']} key{'s' * (vt['count'] != 1)}"
    nw = p.f_hint.getlength(note) / p.px
    d.text(p.s(x0 + pad, y + 10), p.fit(title, p.f_title, width - nw - 10), font=p.f_title,
           fill=(*ACCENT, 255), anchor="lm")
    d.text(p.s(x1 - pad, y + 10), note, font=p.f_hint, fill=muted, anchor="rm")
    y += title_h

    label_w = p.f_day_bold.getlength("Reason") / p.px + 8
    if inside:
        _field(p, d, x0 + pad, x1 - pad, y, "Name", label_w, "vault_name_in", vt["name"],
               "What this key is · Enter", vt["focus"] == "name")
        y += input_h
        _field(p, d, x0 + pad, x1 - pad, y, "Key", label_w, "vault_key_in", vt["secret_dots"],
               "Paste or type it · Enter adds it", vt["focus"] == "secret", mono=True)
    else:
        _field(p, d, x0 + pad, x1 - pad, y, "Reason", label_w, "vault_input", vt["draft"],
               "Why you keep these keys · Enter opens it", True)
    y += input_h + 8

    if skip:
        d.text(p.s(x0 + pad, y + 8), f"{skip} more above · scroll up", font=p.f_hint, fill=muted, anchor="lm")
        y += 16
    if not rows:
        empty = "No keys yet · name one, then paste it" if inside else "No reasons yet · type one"
        d.text(p.s(x0 + pad, y + 17), empty, font=p.f_hint, fill=muted, anchor="lm")
        y += 34
    for i, row in shown:
        rect = (x0 + 6, y, x1 - 6, y + row_h - 2)
        if p.hover == ("vault_row", i):
            p.box(rect, TINT, radius=8, edge=0, shadow=0)
        cy = y + row_h / 2 - 1
        if inside:
            right = row["masked"] + (f"  · {row['expires_in']}" if row["expires_in"] else "")
            rw = p.f_mono.getlength(right) / p.px
            d.text(p.s(x0 + pad, cy), p.fit(row["name"], p.f_day_bold, width - rw - 10), font=p.f_day_bold,
                   fill=ink, anchor="lm")
            d.text(p.s(x1 - pad, cy), right, font=p.f_mono,
                   fill=(*(ALERT if row["expires_in"] else MUTED), 255), anchor="rm")
        else:
            count = f"{row['count']} key{'s' * (row['count'] != 1)}  ›"
            cw = p.f_hint.getlength(count) / p.px
            d.text(p.s(x0 + pad, cy), p.fit(row["name"], p.f_day_bold, width - cw - 10), font=p.f_day_bold,
                   fill=ink, anchor="lm")
            d.text(p.s(x1 - pad, cy), count, font=p.f_hint, fill=muted, anchor="rm")
        p.regions.append(("vault_row", i, rect))
        y += row_h
    if below:
        d.text(p.s(x0 + pad, y + 8), f"{below} more below · scroll down", font=p.f_hint, fill=muted, anchor="lm")

    y = bottom - pad - 18 - buttons_h + 6
    bx = x0 + pad
    buttons = [("vault_back", "‹ Back", CARD), ("vault_add", "Add", PRI), ("vault_paste", "Paste", CARD),
               ("vault_temp", "Temp 24h", PRI if vt["temporary"] else CARD)] if inside else \
        [("vault_add", "Open", PRI), ("vault_paste", "Paste", CARD)]
    for kind, label, fill in buttons + [("vault_done", "Done", CARD)]:
        w = p.f_mini.getlength(label) / p.px + 24
        rect = (bx, y, bx + w, y + 26)
        hovered = p.hover == (kind, None) and fill is CARD
        p.box(p.pressed(kind, None, rect), TINT if hovered else fill, radius=9, edge=2, shadow=2.5)
        d.text(p.s(bx + w / 2, y + 13), label, font=p.f_mini, fill=ink, anchor="mm")
        p.regions.append((kind, None, rect))
        bx += w + 6
    note = vt.get("status") or ("Click a key to copy it (cleared after 45s) · right-click removes" if inside
                                else "Kept on this computer only · never sent to an AI")
    d.text(p.s(x0 + pad, bottom - pad - 6), p.fit(note, p.f_hint, width), font=p.f_hint,
           fill=(*(ALERT if "install" in note.lower() else MUTED), 255), anchor="lm")
