"""PR Review: pick a repo under ~/Projects and a branch: Kiro opens on it with a new chat
asking to review that branch against main/master, typed in but not sent.
Typing narrows the branches, Enter opens the review, Backspace edits the filter (or goes
up), Esc closes."""

from pathlib import Path

from kawaii.cards.base import Card, clamp_skip
from kawaii.features import prreview
from kawaii.input.keys import BTN_LEFT, ENTER, KEY_BACKSPACE, KEY_ESC
from kawaii.input.textfield import printable

CLOSE_AFTER = 3.5  # seconds to read where the prompt went


class PickerCard(Card):
    name = "picker"
    opener = ("action", "review")
    hits = ("pk_row", "pk_back", "pk_open", "pk_cancel")
    scroll_hits = ("pk_card", "pk_row", "pk_filter")

    def __init__(self, screen, reviewer, mover, app_output, head, repos=prreview, home=None, is_dir=Path.is_dir):
        super().__init__(screen)
        self.reviewer, self.mover, self.app_output, self.head = reviewer, mover, app_output, head
        self.repos, self.home, self.is_dir = repos, home or Path.home(), is_dir
        self.step = "folder"  # folder, then branch
        self.path = repos.START  # the folder being browsed
        self.entries = []  # its subfolders [(name, is a repo)]
        self.repo = None  # the repo picked
        self.branches = []  # its branches [(name, is current)]
        self.base = "main"
        self.filter = ""  # typed to narrow the branches
        self.selected = None  # the branch to review
        self.skip = 0  # rows scrolled past
        self.status = ""
        self.close_at = None  # closes itself after a review was handed to Kiro

    def opened(self):
        start = self.repos.START if self.is_dir(self.repos.START) else self.home
        self.step, self.status, self.close_at = "folder", "", None
        self.browse(start)

    def browse(self, path):
        self.path, self.entries, self.skip = path, self.repos.folders(path), 0
        self.screen.redraw()

    def items(self):
        """The rows as the picker draws them (to know what a click hit)."""
        if self.step == "folder":
            return [("up", None)] + [("dir", e) for e in self.entries]
        f = self.filter.lower()
        return [("branch", b) for b, _ in self.branches if f in b.lower()]

    def pick_row(self, i):
        items = self.items()
        if not 0 <= i < len(items):
            return
        kind, item = items[i]
        if kind == "up":
            if self.path != self.home:
                self.browse(self.path.parent)
        elif kind == "dir":
            name, is_repo = item
            path = self.path / name
            if not is_repo:
                self.browse(path)
                return
            found, base = self.repos.branches(path)
            self.step, self.repo, self.branches, self.base, self.filter, self.skip = "branch", path, found, base, "", 0
            self.selected = next((b for b, cur in found if cur), found[0][0] if found else None)
            self.status = "" if found else "No branches found"
            self.screen.redraw()
        else:
            self.selected = item
            self.screen.redraw()

    def open_review(self, rect=None):
        if not self.selected or self.reviewer.busy:
            return
        self.reviewer.start(self.repo, self.selected, self.base)
        # Kiro's window (a new one, or the one already showing this repo) goes to your monitor.
        self.mover.expect(self.app_output(), app="kiro", title=Path(self.repo).name, seconds=45)
        self.status = "Opening Kiro…"
        self.screen.redraw()
        if rect:
            self.fx.tap(rect)

    def back_to_folders(self):
        self.step, self.skip, self.status = "folder", 0, ""
        self.screen.redraw()

    def click(self, hit, button, rect):
        if button != BTN_LEFT:
            return
        if hit[0] == "pk_row":
            self.pick_row(hit[1])
            return
        self.screen.press(hit)
        if hit[0] == "pk_back":
            self.back_to_folders()
        elif hit[0] == "pk_cancel":
            self.close()
        else:
            self.open_review(rect)

    def key(self, key, ctrl):
        if key == KEY_ESC:
            self.close()
        elif key in ENTER and self.step == "branch":
            self.open_review(self.screen.rect("pk_open"))
        elif key == KEY_BACKSPACE:
            if self.step == "branch" and self.filter:
                self.filter = self.filter[:-1]
                self.screen.redraw()
            elif self.step == "branch":
                self.back_to_folders()
            elif self.path != self.home:
                self.browse(self.path.parent)
        return True

    def text(self, text):
        typed = printable(text)
        if typed and self.step == "branch":  # narrows the branch list
            self.filter, self.skip = self.filter + typed, 0
            matches = [b for b, _ in self.branches if self.filter.lower() in b.lower()]
            if matches and self.selected not in matches:
                self.selected = matches[0]
            self.screen.redraw()

    def scroll(self, steps):
        self.skip = clamp_skip(self.skip, steps, self.screen.overlay.pk_rows)
        self.screen.redraw()

    def tick(self, now):
        """Kiro was asked to open the repo with the review prompt (or it failed)."""
        outcome = self.reviewer.poll()
        if outcome:
            ok, message = outcome
            self.status = message
            self.screen.redraw()
            if ok:
                self.close_at = now + CLOSE_AFTER
                self.fx.idea(*self.head(), 1)
        if self.close_at and now >= self.close_at:
            self.close_at = None
            self.close()

    def payload(self):
        return {"open": self.is_open, "step": self.step, "path": self.path, "entries": self.entries,
                "repo": self.repo, "branches": self.branches, "base": self.base, "filter": self.filter,
                "selected": self.selected, "skip": self.skip, "status": self.status}
