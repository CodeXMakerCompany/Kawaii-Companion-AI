"""The bubbles over her head that are not cards: a waiting reminder or alarm, and the voice banner."""

from kawaii.render.painter import CARD, INK, SOFT, PRI, PINK, MUTED, TINT, ALERT, TOP_BAR


def alert(p, d, alerts):
    """The first waiting alert (reminder or system alarm) with its action button."""
    a = alerts[0]
    pad = 12
    x0, x1 = p.left + 16, p.w - 16
    action_w = p.f_mini.getlength(a["action"]) / p.px + 28
    lines = p.wrap(a["title"], p.f_title, x1 - x0 - 2 * pad - action_w - 14)[:2]
    used = pad + 16 + len(lines) * 20 + (14 if len(alerts) > 1 else 0) + pad
    top, bottom, tail = p.bubble_box(used, above=p.card_top)
    p.panel((x0, top, x1, bottom), p.left + p.model_w / 2 if tail else None)
    p.box((x0 + 6, top + 8, x0 + 10, bottom - 8), ALERT, radius=2, edge=0, shadow=0)
    p.regions.append(("alert", None, (x0, top, x1, bottom + (12 if tail else 0))))
    y = top + pad
    d.text(p.s(x0 + pad + 4, y + 6), a["label"], font=p.f_hint, fill=(*ALERT, 255), anchor="lm")
    y += 16
    for ln in lines:
        d.text(p.s(x0 + pad + 4, y + 10), ln, font=p.f_title, fill=(*INK, 255), anchor="lm")
        y += 20
    if len(alerts) > 1:
        d.text(p.s(x0 + pad + 4, y + 6), f"+{len(alerts) - 1} more waiting", font=p.f_hint,
               fill=(*MUTED, 255), anchor="lm")
    rect = (x1 - pad - action_w, (top + bottom) / 2 - 15, x1 - pad, (top + bottom) / 2 + 15)
    p.box(rect, TINT if p.hover == ("alert_action", a["id"]) else PRI, radius=10, edge=2, shadow=2.5)
    d.text(p.s((rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2), a["action"], font=p.f_mini,
           fill=(*INK, 255), anchor="mm")
    p.regions.append(("alert_action", a["id"], rect))


def voice(p, d, v):
    """Mic button (top-left) and a banner with what she heard / is doing / Run-Cancel."""
    ink = (*INK, 255)
    state = v["state"]
    cx, cy, r = 25, 20, 13
    fill = {"listening": PINK, "thinking": (255, 200, 90), "confirm": PRI}.get(state)
    if fill is None:
        fill = TINT if p.hover == ("mic", None) else CARD
    p.circle(cx, cy, r, fill, shadow=2)
    lw = max(1, round(2 * p.px))
    p.box((cx - 3.5, cy - 8, cx + 3.5, cy + 2), INK, radius=3.5, edge=0, shadow=0)
    d.arc(p.s(cx - 7, cy - 6, cx + 7, cy + 5), start=0, end=180, fill=ink, width=lw)
    d.line(p.s(cx, cy + 5, cx, cy + 8), fill=ink, width=lw)
    d.line(p.s(cx - 4, cy + 8.5, cx + 4, cy + 8.5), fill=ink, width=lw)
    p.regions.append(("mic", None, (cx - r - 2, cy - r - 2, cx + r + 2, cy + r + 2)))

    text = v.get("text")
    if not text:
        return
    x0, x1, pad = 12, p.w - 12, 10
    confirm = state == "confirm" and v.get("command")
    h = 30 + (52 if confirm else 0)
    top = TOP_BAR + 2
    p.box((x0, top, x1, top + h), radius=12, edge=2.5, shadow=4)
    p.regions.append(("voice_banner", None, (x0, top, x1, top + h)))
    color = (*ALERT, 255) if v.get("error") else ink
    d.text(p.s(x0 + pad, top + 15), p.fit(text, p.f_hint, x1 - x0 - 2 * pad), font=p.f_hint,
           fill=color, anchor="lm")
    if not confirm:
        return
    y = top + 30
    p.box((x0 + pad, y, x1 - pad, y + 20), INK, radius=6, edge=0, shadow=0)
    d.text(p.s(x0 + pad + 8, y + 10), p.fit("$ " + v["command"], p.f_hint, x1 - x0 - 2 * pad - 16),
           font=p.f_hint, fill=(*SOFT, 255), anchor="lm")
    y += 24
    bx = x1 - pad
    for kind, label, base in (("voice_cancel", "Cancel", CARD), ("voice_run", "Run", PRI)):
        w = p.f_mini.getlength(label) / p.px + 26
        rect = (bx - w, y, bx, y + 22)
        p.box(rect, TINT if p.hover == (kind, None) else base, radius=8, edge=2, shadow=2)
        d.text(p.s(rect[0] + w / 2, y + 11), label, font=p.f_mini, fill=ink, anchor="mm")
        p.regions.append((kind, None, rect))
        bx -= w + 6
    note = "Run once (or say yes) to approve: it is then remembered" if v.get("ai") else "Say yes or press Run"
    d.text(p.s(x0 + pad, y + 11), p.fit(note, p.f_hint, bx - x0 - pad - 6), font=p.f_hint,
           fill=(*MUTED, 255), anchor="lm")
