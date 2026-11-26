"""How the PR Review picker card is drawn: draw(painter, ImageDraw, the card's payload)."""

from pathlib import Path

from kawaii.render.painter import CARD, INK, SOFT, PRI, ACCENT, MUTED, TINT, TRACK, TOP_BAR

FOOTER = "Esc  ·  close PR review"


def draw(p, d, pk):
    """PR review: a small folder browser from ~/Projects (a repo goes on to its branches),
    then the branch to review, compared with main or master. Opening hands it to Kiro."""
    ink, muted = (*INK, 255), (*MUTED, 255)
    pad, x0, x1 = 12, p.left + 16, p.w - 16
    width = x1 - x0 - 2 * pad
    folder_step = pk["step"] == "folder"
    if folder_step:
        items = [("up", "..", False)] + [("dir", n, repo) for n, repo in pk["entries"]]
    else:
        f = pk["filter"].lower()
        items = [("branch", b, cur) for b, cur in pk["branches"] if f in b.lower()]
    p.pk_rows = len(items)

    title_h, info_h, row_h, buttons_h = 28, 22, 24, 36
    filter_h = 0 if folder_step else 32
    fixed = pad + title_h + info_h + filter_h + buttons_h + pad + 18
    max_h = p.h - TOP_BAR - 50
    skip = max(0, min(pk.get("skip", 0), len(items) - 1)) if items else 0
    fit = max(1, int((max_h - fixed) // row_h))
    shown = items[skip:skip + fit]
    used = fixed + max(1, len(shown)) * row_h
    top, bottom, tail = p.bubble_box(used)
    p.panel((x0, top, x1, bottom), p.left + p.model_w / 2 if tail else None)
    p.regions.append(("pk_card", None, (x0, top, x1, bottom + (12 if tail else 0))))
    p.card_top, p.card_bottom = top, bottom

    y = top + pad
    d.text(p.s(x0 + pad, y + 10), "PR review", font=p.f_title, fill=(*ACCENT, 255), anchor="lm")
    d.text(p.s(x1 - pad, y + 10), "pick a repo folder" if folder_step else "pick the branch to review",
           font=p.f_hint, fill=muted, anchor="rm")
    y += title_h
    if folder_step:
        home = str(Path.home())
        where = str(pk["path"]).replace(home, "~", 1)
        d.text(p.s(x0 + pad, y + 9), p.fit(where, p.f_day_bold, width), font=p.f_day_bold, fill=ink,
               anchor="lm")
    else:
        name = Path(pk["repo"]).name
        d.text(p.s(x0 + pad, y + 9), name, font=p.f_day_bold, fill=ink, anchor="lm")
        nw = p.f_day_bold.getlength(name) / p.px
        d.text(p.s(x0 + pad + nw + 8, y + 9), f"compared with {pk['base']}", font=p.f_hint, fill=muted,
               anchor="lm")
    y += info_h
    if not folder_step:  # type to narrow the branches down
        field = (x0 + pad, y, x1 - pad, y + 26)
        p.box(field, radius=8, edge=2, shadow=2)
        p.regions.append(("pk_filter", None, field))
        if pk["filter"]:
            d.text(p.s(field[0] + 10, y + 13), p.fit(pk["filter"], p.f_item, width - 24),
                   font=p.f_item, fill=ink, anchor="lm")
        else:
            d.text(p.s(field[0] + 10, y + 13), "Type to filter branches", font=p.f_hint, fill=muted,
                   anchor="lm")
        caret = field[0] + 10 + p.f_item.getlength(pk["filter"]) / p.px + 1
        p.caret = (caret, y + 13)
        d.line(p.s(caret, y + 6, caret, y + 20), fill=ink, width=max(1, round(2 * p.px)))
        y += filter_h

    if skip:
        d.text(p.s(x1 - pad, y - 4), "more above", font=p.f_hint, fill=muted, anchor="rs")
    if not shown:
        d.text(p.s(x0 + pad, y + row_h / 2), "No folders here" if folder_step else "No branch matches",
               font=p.f_hint, fill=muted, anchor="lm")
    for i, (kind, label, flag) in enumerate(shown, skip):
        rect = (x0 + 6, y, x1 - 6, y + row_h - 2)
        selected = kind == "branch" and label == pk.get("selected")
        if selected:
            p.box(rect, PRI, radius=7, edge=2, shadow=0)
        elif p.hover == ("pk_row", i):
            p.box(rect, TINT, radius=7, edge=0, shadow=0)
        if kind == "up":
            d.text(p.s(x0 + pad + 4, y + 11), "..  up a folder", font=p.f_hint, fill=muted, anchor="lm")
        else:
            d.text(p.s(x0 + pad + 4, y + 11), p.fit(label, p.f_day, width - 70), font=p.f_day,
                   fill=ink, anchor="lm")
            tag = ("git" if flag else None) if kind == "dir" else ("current" if flag else None)
            if tag:
                tw = p.f_hint.getlength(tag) / p.px + 12
                p.box((x1 - pad - tw, y + 4, x1 - pad, y + row_h - 6), SOFT if kind == "dir" else TINT,
                          radius=6, edge=1.2, shadow=0)
                d.text(p.s(x1 - pad - tw / 2, y + 11), tag, font=p.f_hint, fill=ink, anchor="mm")
        p.regions.append(("pk_row", i, rect))
        y += row_h
    if len(items) > skip + len(shown):
        d.text(p.s(x1 - pad, y + 8), f"{len(items) - skip - len(shown)} more below · scroll", font=p.f_hint,
               fill=muted, anchor="rm")
    y = bottom - pad - buttons_h + 6

    bx = x0 + pad
    buttons = [("pk_cancel", "Cancel", CARD)] if folder_step else \
        [("pk_back", "Back", CARD), ("pk_open", "Open in Kiro", PRI if pk.get("selected") else TRACK)]
    for kind, label, fill in buttons:
        w = p.f_mini.getlength(label) / p.px + 24
        rect = (bx, y, bx + w, y + 26)
        hovered = p.hover == (kind, None) and fill == CARD
        p.box(p.pressed(kind, None, rect), TINT if hovered else fill, radius=9, edge=2, shadow=2.5)
        d.text(p.s(bx + w / 2, y + 13), label, font=p.f_mini, fill=ink, anchor="mm")
        p.regions.append((kind, None, rect))
        bx += w + 6
    if pk.get("status"):
        d.text(p.s(x1 - pad, y + 13), p.fit(pk["status"], p.f_hint, x1 - pad - bx - 6), font=p.f_hint,
               fill=muted, anchor="rm")
