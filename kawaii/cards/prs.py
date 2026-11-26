"""The pull-request comments card, opened from the GitHub badge (read only). Closing it
marks them read, and the badge goes."""

from kawaii.cards.base import Card, clamp_skip, clock
from kawaii.input.keys import KEY_ESC


class PRCard(Card):
    name = "prs"
    opener = ("gh_badge", None)
    scroll_hits = ("pr_card", "gh_badge")

    def __init__(self, screen, prs):
        super().__init__(screen)
        self.prs = prs
        self.skip = 0  # rows scrolled past

    def opened(self):
        self.skip = 0

    def closed(self):
        self.skip = 0
        self.prs.mark_read()

    def key(self, key, ctrl):
        if key == KEY_ESC:  # only Esc: her hotkeys keep working under it
            self.close()
            return True
        return False

    def scroll(self, steps):
        self.skip = clamp_skip(self.skip, steps, self.screen.overlay.pr_rows)
        self.screen.redraw()

    def payload(self):
        return {"open": self.is_open, "items": self.prs.unread, "skip": self.skip,
                "checked": clock(self.prs.checked_at)}
