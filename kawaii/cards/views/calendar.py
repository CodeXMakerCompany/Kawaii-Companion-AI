"""How the Calendar card is drawn: draw(painter, ImageDraw, the card's payload)."""

import calendar
import datetime

from kawaii.render.painter import CARD, INK, PRI, ACCENT, MUTED, TINT, TRACK, ALERT

FOOTER = "Esc  ·  close the calendar"


def draw(p, d, cal):
    """Month grid to pick a date, a title field, Add/Update and the reminder list."""
    ink = (*INK, 255)
    pad, cell_h, row_h = 12, 24, 22
    x0, x1 = p.left + 16, p.w - 16
    year, month = cal["month"]
    today = cal["today"]
    weeks = calendar.Calendar(0).monthdatescalendar(year, month)
    events = cal["events"]
    listing = events.listing(today)
    marked = events.marked_days(year)
    shown_rows = listing[:4]
    used = (pad + 26 + 16 + len(weeks) * cell_h + 8 + 30 + 6 + 28 + 10 + 16
            + max(1, len(shown_rows)) * row_h + (16 if len(listing) > len(shown_rows) else 0) + pad)
    top, bottom, tail = p.bubble_box(used)
    cx_tail = p.left + p.model_w / 2
    p.panel((x0, top, x1, bottom), cx_tail if tail else None)
    p.regions.append(("cal_card", None, (x0, top, x1, bottom + (12 if tail else 0))))
    p.card_top, p.card_bottom = top, bottom

    # Month header with prev/next arrows.
    y = top + pad
    d.text(p.s((x0 + x1) / 2, y + 13), datetime.date(year, month, 1).strftime("%B %Y"), font=p.f_title,
           fill=ink, anchor="mm")
    for kind, ax in (("cal_prev", x0 + pad), ("cal_next", x1 - pad - 26)):
        rect = (ax, y, ax + 24, y + 24)
        p.box(rect, TINT if p.hover == (kind, None) else CARD, radius=8, edge=2, shadow=2)
        mx, my = ax + 12, y + 12
        tri = (mx + 3, my - 5, mx + 3, my + 5, mx - 4, my) if kind == "cal_prev" else \
            (mx - 3, my - 5, mx - 3, my + 5, mx + 4, my)
        p.poly(tri, INK)
        p.regions.append((kind, None, rect))
    y += 26

    cw = (x1 - x0 - 2 * pad) / 7
    for i, name in enumerate(("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")):
        d.text(p.s(x0 + pad + i * cw + cw / 2, y + 7), name, font=p.f_hint, fill=(*MUTED, 255), anchor="mm")
    y += 16

    for week in weeks:
        for i, day in enumerate(week):
            iso = day.isoformat()
            rect = (x0 + pad + i * cw + 2, y + 1, x0 + pad + (i + 1) * cw - 2, y + cell_h - 1)
            selected, is_today = iso == cal["selected"], day == today
            if selected:
                p.box(rect, PRI, radius=7, edge=2, shadow=0)
            elif p.hover == ("cal_day", iso):
                p.box(rect, TINT, radius=7, edge=0, shadow=0)
            color = ink if selected else (*ACCENT, 255) if is_today else \
                ink if day.month == month else (*MUTED, 255)
            font = p.f_day_bold if is_today else p.f_day
            cx, cy = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
            d.text(p.s(cx, cy - (2 if iso in marked else 0)), str(day.day), font=font, fill=color, anchor="mm")
            if iso in marked:  # a reminder to do on this day; red once it is due
                dot = INK if selected else ALERT if iso <= today.isoformat() else ACCENT
                p.circle(cx, cy + 8, 2.2, dot, edge=0)
            p.regions.append(("cal_day", iso, rect))
        y += cell_h
    y += 8

    # Selected date + title field.
    label = datetime.date.fromisoformat(cal["selected"]).strftime("%a %d %b")
    lw = p.f_title.getlength(label) / p.px
    d.text(p.s(x0 + pad, y + 13), label, font=p.f_title, fill=ink, anchor="lm")
    field = (x0 + pad + lw + 10, y, x1 - pad, y + 26)
    p.box(field, radius=8, edge=2, shadow=2)
    limit = field[2] - field[0] - 20
    shown = cal["draft"]
    while shown and p.f_item.getlength(shown) > limit * p.px:
        shown = shown[1:]
    tx, ty = field[0] + 10, y + 13
    if shown:
        d.text(p.s(tx, ty), shown, font=p.f_item, fill=(*INK, 255), anchor="lm")
    else:
        d.text(p.s(tx + 2, ty), p.fit("Reminder title", p.f_item, limit), font=p.f_item,
               fill=(*MUTED, 255), anchor="lm")
    caret = tx + p.f_item.getlength(shown) / p.px + 1
    p.caret = (caret, ty)
    d.line(p.s(caret, ty - 8, caret, ty + 8), fill=ink, width=max(1, round(2 * p.px)))
    p.regions.append(("cal_input", None, field))
    y += 30 + 6

    # Add / Update, and while editing: New, Delete.
    editing = cal["editing"]
    bx = x0 + pad
    for kind, text, fill, color in (("cal_save", "Update" if editing else "Add reminder", PRI, INK),
                                    ("cal_new", "New", CARD, INK) if editing else (None,) * 4,
                                    ("cal_delete", "Delete", CARD, ALERT) if editing else (None,) * 4):
        if not kind:
            continue
        w = p.f_mini.getlength(text) / p.px + 28
        rect = (bx, y, bx + w, y + 26)
        p.box(p.pressed(kind, None, rect), TINT if p.hover == (kind, None) and fill == CARD else fill,
                  radius=10, edge=2, shadow=2.5)
        d.text(p.s(bx + w / 2, y + 13), text, font=p.f_mini, fill=(*color, 255), anchor="mm")
        p.regions.append((kind, None, rect))
        bx += w + 6
    # Yearly switch: a small track + knob, right-aligned on the same row.
    sw_x1 = x1 - pad
    label_w = p.f_hint.getlength("Yearly") / p.px
    track = (sw_x1 - 34, y + 6, sw_x1, y + 22)
    on = cal.get("yearly", False)
    p.box(track, PRI if on else TRACK, radius=8, edge=2, shadow=0)
    kx = track[2] - 9 if on else track[0] + 9
    p.circle(kx, y + 14, 6.5, CARD, edge=2)
    d.text(p.s(track[0] - 6, y + 14), "Yearly", font=p.f_hint, fill=ink, anchor="rm")
    p.regions.append(("cal_yearly", None, (track[0] - label_w - 10, y, sw_x1, y + 28)))
    y += 28 + 10

    # Reminder list: click edits, the box marks done, right-click deletes.
    d.text(p.s(x0 + pad, y + 6), "REMINDERS", font=p.f_hint, fill=(*MUTED, 255), anchor="lm")
    hint = "click: edit · right-click: delete"
    if p.f_hint.getlength(hint) / p.px + 90 < x1 - x0 - 2 * pad:
        d.text(p.s(x1 - pad, y + 6), hint, font=p.f_hint, fill=(*MUTED, 255), anchor="rm")
    y += 16
    if not shown_rows:
        d.text(p.s(x0 + pad, y + row_h / 2), "Pick a date, type a title, Add reminder", font=p.f_hint,
               fill=(*MUTED, 255), anchor="lm")
    iso_today = today.isoformat()
    for e in shown_rows:
        row = (x0 + 6, y, x1 - 6, y + row_h)
        if e["id"] == editing or p.hover == ("cal_event", e["id"]):
            p.box(row, TINT, radius=6, edge=0, shadow=0)
        p.regions.append(("cal_event", e["id"], row))
        bx, by = x0 + pad, y + 4
        box = (bx - 2, by - 2, bx + 16, by + 16)
        finished = events.is_done(e)
        p.checkbox(bx, by, 14, finished)
        p.regions.append(("cal_done", e["id"], box))
        occ = events.when(e, today)
        due = not finished and occ <= today
        when = occ.strftime("%a %d %b") + ("" if occ.year == today.year else f" {occ.year % 100:02d}")
        d.text(p.s(bx + 22, y + row_h / 2), when, font=p.f_hint,
               fill=(*ALERT, 255) if due else (*MUTED, 255) if finished else (*ACCENT, 255), anchor="lm")
        title_x = bx + 22 + 88
        tag_w = (p.f_hint.getlength("yearly") / p.px + 12) if e["yearly"] else 0
        title = p.fit(e["title"], p.f_day, x1 - pad - title_x - tag_w)
        color = (*MUTED, 255) if finished else ink
        d.text(p.s(title_x, y + row_h / 2), title, font=p.f_day, fill=color, anchor="lm")
        if e["yearly"]:  # small tag at the end of the row
            tx1 = x1 - pad
            p.box((tx1 - tag_w + 2, y + 3, tx1, y + row_h - 3), TINT, radius=7, edge=1.2, shadow=0)
            d.text(p.s(tx1 - (tag_w - 2) / 2, y + row_h / 2), "yearly", font=p.f_hint,
                   fill=(*ACCENT, 255), anchor="mm")
        if finished:
            d.line(p.s(title_x, y + row_h / 2, title_x + p.f_day.getlength(title) / p.px, y + row_h / 2),
                   fill=color, width=max(1, round(p.px)))
        y += row_h
    if len(listing) > len(shown_rows):
        d.text(p.s(x0 + pad + 22, y + 7), f"+{len(listing) - len(shown_rows)} more", font=p.f_hint,
               fill=(*MUTED, 255), anchor="lm")
