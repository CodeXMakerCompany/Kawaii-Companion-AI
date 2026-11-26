"""How the Business Rules card is drawn: draw(painter, ImageDraw, the card's payload)."""

from kawaii.render.painter import CARD, INK, PRI, ACCENT, MUTED, TINT, ALERT, TOP_BAR

FOOTER = "Esc  ·  close Business Rules"


def draw(p, d, rb):
    """Business Rules: the list of companies (type a name, Enter opens it, new or not), and
    inside one, its rules as a numbered list (type a rule, Enter adds it)."""
    ink, muted = (*INK, 255), (*MUTED, 255)
    pad, x0, x1 = 12, p.left + 16, p.w - 16
    width = x1 - x0 - 2 * pad
    companies, ci = rb["companies"], rb["company"]
    company = companies[ci] if ci is not None else None
    line_h, title_h, input_h, buttons_h = 17, 28, 30, 34
    fixed = pad + title_h + input_h + 8 + buttons_h + 18 + pad
    max_h = p.h - TOP_BAR - 50
    num_w = 26  # room for "12." before each rule
    if company:  # rules wrap: every row is as tall as its lines
        items = [(i, p.wrap(r["text"], p.f_day, width - num_w - 8)[:4])
                 for i, r in enumerate(company["rules"])]
    else:
        items = [(i, None) for i in range(len(companies))]
    row_h = (lambda lines: len(lines) * line_h + 10) if company else (lambda lines: 34)
    room = max_h - fixed - 32
    skip = rb.get("skip", 0)
    if skip is None:  # scrolled to the end: as many of the last rows as fit
        skip, h = len(items), 0
        while skip and h + row_h(items[skip - 1][1]) <= room:
            skip -= 1
            h += row_h(items[skip][1])
    skip = max(0, min(skip, len(items) - 1)) if items else 0
    p.rules_rows, p.rules_skip = len(items), skip
    room = max_h - fixed - (16 if skip else 0) - 16
    shown, used_rows = [], 0
    for i, lines in items[skip:]:
        h = row_h(lines)
        if shown and used_rows + h > room:
            break
        shown.append((i, lines, h))
        used_rows += h
    below = len(items) - skip - len(shown)
    used = fixed + max(34, used_rows) + (16 if skip else 0) + (16 if below else 0)
    top, bottom, tail = p.bubble_box(used)
    p.panel((x0, top, x1, bottom), p.left + p.model_w / 2 if tail else None)
    p.regions.append(("rules_card", None, (x0, top, x1, bottom + (12 if tail else 0))))
    p.card_top, p.card_bottom = top, bottom

    y = top + pad
    if company:
        n = len(company["rules"])
        title, note = company["name"], f"{n} rule{'s' * (n != 1)}"
    else:
        n = len(companies)
        title, note = "Business Rules", f"{n} compan{'ies' if n != 1 else 'y'}"
    nw = p.f_hint.getlength(note) / p.px
    d.text(p.s(x0 + pad, y + 10), p.fit(title, p.f_title, width - nw - 10), font=p.f_title,
           fill=(*ACCENT, 255), anchor="lm")
    d.text(p.s(x1 - pad, y + 10), note, font=p.f_hint, fill=muted, anchor="rm")
    y += title_h

    label, hint = ("Rule", "Write a rule · Enter adds it") if company else \
        ("Company", "A company name · Enter opens it")
    label_w = p.f_day_bold.getlength("Company") / p.px + 8
    d.text(p.s(x0 + pad, y + 13), label, font=p.f_day_bold, fill=ink, anchor="lm")
    field = (x0 + pad + label_w, y, x1 - pad, y + 26)
    p.box(field, TINT, radius=8, edge=2.5, shadow=2)
    p.regions.append(("rules_input", None, field))
    tx, cy = field[0] + 10, (field[1] + field[3]) / 2
    space = field[2] - field[0] - 24
    text = rb["draft"]
    if text:
        shown_text = text
        while shown_text and p.f_day.getlength(shown_text) > space * p.px:
            shown_text = shown_text[1:]  # the end stays in view, where the caret is
        d.text(p.s(tx, cy), shown_text, font=p.f_day, fill=ink, anchor="lm")
        caret = tx + p.f_day.getlength(shown_text) / p.px + 1
    else:
        d.text(p.s(tx, cy), p.fit(hint, p.f_hint, space), font=p.f_hint, fill=muted, anchor="lm")
        caret = tx
    p.caret = (caret, cy)
    d.line(p.s(caret, cy - 7, caret, cy + 7), fill=ink, width=max(1, round(2 * p.px)))
    y += input_h + 8

    if skip:
        d.text(p.s(x0 + pad, y + 8), f"{skip} more above · scroll up", font=p.f_hint, fill=muted,
               anchor="lm")
        y += 16
    if not items:
        empty = "No rules yet · start writing" if company else "No companies yet · type a name"
        d.text(p.s(x0 + pad, y + 17), empty, font=p.f_hint, fill=muted, anchor="lm")
        y += 34
    for i, lines, h in shown:
        rect = (x0 + 6, y, x1 - 6, y + h - 2)
        if p.hover == ("rules_row", i):
            p.box(rect, TINT, radius=8, edge=0, shadow=0)
        if company:
            d.text(p.s(x0 + pad, y + 5), f"{i + 1}.", font=p.f_day_bold, fill=(*ACCENT, 255))
            for k, ln in enumerate(lines):
                d.text(p.s(x0 + pad + num_w, y + 5 + k * line_h), ln, font=p.f_day, fill=ink)
        else:
            c = companies[i]
            count = f"{len(c['rules'])} rule{'s' * (len(c['rules']) != 1)}  ›"
            cw = p.f_hint.getlength(count) / p.px
            d.text(p.s(x0 + pad, y + h / 2 - 1), p.fit(c["name"], p.f_day_bold, width - cw - 10),
                   font=p.f_day_bold, fill=ink, anchor="lm")
            d.text(p.s(x1 - pad, y + h / 2 - 1), count, font=p.f_hint, fill=muted, anchor="rm")
        p.regions.append(("rules_row", i, rect))
        y += h
    if below:
        d.text(p.s(x0 + pad, y + 8), f"{below} more below · scroll down", font=p.f_hint, fill=muted,
               anchor="lm")

    y = bottom - pad - 18 - buttons_h + 6
    bx = x0 + pad
    back = [] if rb.get("locked") else [("rules_back", "‹ Back", CARD)]  # one client's rules: no list to go back to
    buttons = back + [("rules_add", "Add", PRI), ("rules_paste", "Paste", CARD),
                      ("rules_copy", "Copy all", CARD)] if company else \
        [("rules_add", "Open", PRI), ("rules_paste", "Paste", CARD)]
    for kind, label, fill in buttons + [("rules_done", "Done", CARD)]:
        w = p.f_mini.getlength(label) / p.px + 24
        rect = (bx, y, bx + w, y + 26)
        hovered = p.hover == (kind, None)
        p.box(p.pressed(kind, None, rect), TINT if hovered else fill, radius=9, edge=2, shadow=2.5)
        d.text(p.s(bx + w / 2, y + 13), label, font=p.f_mini, fill=ink, anchor="mm")
        p.regions.append((kind, None, rect))
        bx += w + 6
    note = rb.get("status") or ("Click a rule to copy it · right-click removes it" if company
                                else "Click a company to open it · right-click removes it")
    d.text(p.s(x0 + pad, bottom - pad - 6), p.fit(note, p.f_hint, width), font=p.f_hint,
           fill=(*(ALERT if "install" in note.lower() else MUTED), 255), anchor="lm")
