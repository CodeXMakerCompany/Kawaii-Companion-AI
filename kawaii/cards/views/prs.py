"""How the pull-request comments card is drawn: draw(painter, ImageDraw, the card's payload)."""

from kawaii.render.painter import INK, ACCENT, MUTED, TINT, TOP_BAR, ago

FOOTER = "Esc  ·  close the comments"


def draw(p, d, pr):
    """The new comments on your pull requests, grouped by PR (latest activity first), to
    read and see which repo they are in. Read only: nothing here writes to GitHub."""
    ink, muted = (*INK, 255), (*MUTED, 255)
    pad, x0, x1 = 12, p.left + 16, p.w - 16
    width = x1 - x0 - 2 * pad
    groups = {}
    for c in reversed(pr["items"]):  # newest first, so each PR sits where its latest comment is
        groups.setdefault((c["repo"], c["number"]), []).append(c)

    rows = []  # (kind, height, data)
    for (repo, number), comments in groups.items():
        heading = ("pr", 22, (repo, number, comments[0]["title"]))
        rows.append(heading)
        for c in comments:
            body = " ".join(c["body"].replace("```", " ").split())
            if not body and c["kind"] == "review":
                body = {"APPROVED": "Approved", "CHANGES_REQUESTED": "Requested changes"}.get(c.get("state"), "")
            lines = p.wrap(body, p.f_hint, width - 10)[:3] if body else []
            if len(lines) == 3:
                lines[2] = p.fit(lines[2] + " …", p.f_hint, width - 10)
            rows.append(("comment", 18 + 15 * len(lines) + 6, (c, lines), heading))

    max_h = p.h - TOP_BAR - 50  # reading them is worth covering her for a moment
    title_h = 30
    skip = max(0, min(pr.get("skip", 0), len(rows) - 1))
    p.pr_rows = len(rows)  # for scrolling
    used, shown = pad + title_h + pad + (18 if skip else 0), []
    if rows and rows[skip][0] == "comment":  # scrolled into a PR: keep its heading on top
        shown.append(rows[skip][3])
        used += rows[skip][3][1]
    for i, row in enumerate(rows[skip:], skip):
        more = 18 if i < len(rows) - 1 else 0
        if used + row[1] + more > max_h:
            break
        shown.append(row)
        used += row[1]
    above = sum(1 for r in rows[:skip] if r[0] == "comment")
    hidden = sum(1 for r in rows[skip + len(shown):] if r[0] == "comment")
    if hidden:
        used += 18
    top, bottom, tail = p.bubble_box(used)
    p.panel((x0, top, x1, bottom), p.left + p.model_w / 2 if tail else None)
    p.regions.append(("pr_card", None, (x0, top, x1, bottom + (12 if tail else 0))))
    p.card_top, p.card_bottom = top, bottom

    y = top + pad
    n = len(pr["items"])
    d.text(p.s(x0 + pad, y + 10), f"Pull requests · {n} new comment{'s' * (n != 1)}", font=p.f_title,
           fill=(*ACCENT, 255), anchor="lm")
    if pr.get("checked"):
        d.text(p.s(x1 - pad, y + 10), f"checked {pr['checked']}", font=p.f_hint, fill=muted, anchor="rm")
    y += title_h
    if above:
        d.text(p.s(x0 + pad, y + 9), f"{above} more above · scroll up", font=p.f_hint, fill=muted, anchor="lm")
        y += 18
    for kind, h, data, *_ in shown:
        if kind == "pr":  # which repo and PR: the place to go and check
            repo, number, title = data
            p.box((x0 + 6, y, x1 - 6, y + 18), TINT, radius=6, edge=0, shadow=0)
            label = f"{repo} #{number}"
            d.text(p.s(x0 + pad, y + 9), label, font=p.f_day_bold, fill=ink, anchor="lm")
            lw = p.f_day_bold.getlength(label) / p.px
            d.text(p.s(x0 + pad + lw + 8, y + 9), p.fit(title, p.f_hint, width - lw - 10),
                   font=p.f_hint, fill=muted, anchor="lm")
        else:
            c, lines = data
            what = {"review": "review", "inline": f"on {c.get('path', '').split('/')[-1]}"
                    + (f":{c['line']}" if c.get("line") else ""), "comment": "comment"}[c["kind"]]
            who = c["author"]
            d.text(p.s(x0 + pad + 4, y + 9), who, font=p.f_day_bold, fill=(*ACCENT, 255), anchor="lm")
            ww = p.f_day_bold.getlength(who) / p.px
            d.text(p.s(x0 + pad + 4 + ww + 6, y + 9), p.fit(f"{what} · {ago(c['at'])}", p.f_hint,
                                                                    width - ww - 12),
                   font=p.f_hint, fill=muted, anchor="lm")
            for i, ln in enumerate(lines):
                d.text(p.s(x0 + pad + 4, y + 18 + 15 * i + 7), ln, font=p.f_hint, fill=ink, anchor="lm")
        y += h
    if hidden:
        d.text(p.s(x0 + pad, y + 9), f"{hidden} more below · scroll down", font=p.f_hint, fill=muted, anchor="lm")
