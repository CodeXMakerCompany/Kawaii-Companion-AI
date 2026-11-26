"""How the Settings card is drawn: draw(painter, ImageDraw, the card's payload)."""

from kawaii.render.painter import INK, SOFT, PRI, ACCENT, MUTED, TINT, ALERT

FOOTER = "Esc  ·  close Settings"


def draw(p, d, st):
    """Settings: which monitor the apps she opens go to (Kiro from PR Review, apps opened by
    voice). 'Largest' follows whichever monitor is biggest, even after they change."""
    ink, muted = (*INK, 255), (*MUTED, 255)
    pad, x0, x1 = 12, p.left + 16, p.w - 16
    width = x1 - x0 - 2 * pad
    rows = [("auto", "Largest monitor", f"now {st['largest']}" if st["largest"] else "")]
    rows += [(name, name, f"{model} · {w}×{h}" if model else f"{w}×{h}") for name, w, h, model in st["monitors"]]
    row_h = 28
    used = pad + 28 + 34 + len(rows) * row_h + (18 if not st["available"] else 0) + 8 + 34 + pad
    top, bottom, tail = p.bubble_box(used)
    p.panel((x0, top, x1, bottom), p.left + p.model_w / 2 if tail else None)
    p.regions.append(("set_card", None, (x0, top, x1, bottom + (12 if tail else 0))))
    p.card_top, p.card_bottom = top, bottom

    y = top + pad
    d.text(p.s(x0 + pad, y + 10), "Settings", font=p.f_title, fill=(*ACCENT, 255), anchor="lm")
    y += 28
    d.text(p.s(x0 + pad, y + 8), "Open apps on", font=p.f_day_bold, fill=ink, anchor="lm")
    d.text(p.s(x0 + pad, y + 24), p.fit("Kiro from PR Review, and apps she opens for you", p.f_hint,
                                               width), font=p.f_hint, fill=muted, anchor="lm")
    y += 34
    for i, (key, label, detail) in enumerate(rows):
        rect = (x0 + 6, y, x1 - 6, y + row_h - 3)
        if key == st["choice"]:
            p.box(rect, PRI, radius=8, edge=2, shadow=0)
        elif p.hover == ("set_mon", i):
            p.box(rect, TINT, radius=8, edge=0, shadow=0)
        d.text(p.s(x0 + pad + 4, y + 12), label, font=p.f_day_bold if key == "auto" else p.f_day,
               fill=ink, anchor="lm")
        lw = (p.f_day_bold if key == "auto" else p.f_day).getlength(label) / p.px
        d.text(p.s(x0 + pad + 4 + lw + 8, y + 12), detail, font=p.f_hint, fill=muted, anchor="lm")
        tags = [] if key == "auto" else [t for t, on in (("largest", key == st["largest"]),
                                                         ("she's here", key == st["here"])) if on]
        tx = x1 - pad
        for tag in reversed(tags):
            tw = p.f_hint.getlength(tag) / p.px + 12
            p.box((tx - tw, y + 4, tx, y + row_h - 7), SOFT if tag == "largest" else TINT, radius=6,
                      edge=1.2, shadow=0)
            d.text(p.s(tx - tw / 2, y + 11), tag, font=p.f_hint, fill=ink, anchor="mm")
            tx -= tw + 4
        p.regions.append(("set_mon", i, rect))
        y += row_h
    if not st["available"]:
        d.text(p.s(x0 + pad, y + 9), "Moving windows needs the COSMIC desktop", font=p.f_hint, fill=(*ALERT, 255),
               anchor="lm")
        y += 18
    y = bottom - pad - 28
    w = p.f_mini.getlength("Done") / p.px + 28
    rect = (x0 + pad, y, x0 + pad + w, y + 26)
    p.box(p.pressed("set_done", None, rect), TINT if p.hover == ("set_done", None) else PRI, radius=9,
              edge=2, shadow=2.5)
    d.text(p.s(rect[0] + w / 2, y + 13), "Done", font=p.f_mini, fill=ink, anchor="mm")
    p.regions.append(("set_done", None, rect))
