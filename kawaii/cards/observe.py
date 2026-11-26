"""Observability: the endpoints she GETs every 20 minutes (she speaks up when one stops
answering). Tab switches field, Enter adds (from Title: goes to URL), click copies a URL,
right-click removes it, Ctrl+V pastes, Esc closes."""

from kawaii.cards.base import Card, clamp_skip, clock
from kawaii.input.keys import BTN_LEFT, BTN_RIGHT, ENTER, KEY_BACKSPACE, KEY_C, KEY_ESC, KEY_TAB, KEY_V
from kawaii.input.textfield import erase, printable

NO_CLIPBOARD = "Install wl-clipboard to copy and paste"


class ObserveCard(Card):
    name = "observe"
    opener = ("button", "observe")
    open_fx = "pop"
    hits = ("obs_add", "obs_paste", "obs_check", "obs_done", "obs_row", "obs_title_in", "obs_input")
    scroll_hits = ("obs_card", "obs_row", "obs_input")

    def __init__(self, screen, pinger, clipboard):
        super().__init__(screen)
        self.pinger, self.clipboard = pinger, clipboard
        self.draft = ""  # the URL being typed
        self.title = ""  # its title
        self.focus = "title"  # which field typing goes to: title or url
        self.status = ""  # a short note: Copied!, why paste failed
        self.skip = 0  # endpoint rows scrolled past

    def _reset(self):
        self.skip, self.focus, self.status = 0, "title", ""

    opened = closed = _reset

    def _field(self):
        return "draft" if self.focus == "url" else "title"

    def add(self, rect=None):
        if not self.draft.strip():
            self.focus, self.status = "url", "Type the URL too"
        elif self.pinger.add(self.draft, self.title):
            self.draft, self.title, self.focus, self.status = "", "", "title", ""
            if rect:
                self.fx.done(rect)
        else:
            self.status = "That URL is already watched"
        self.screen.redraw()

    def paste(self):
        """Into the field being typed in (a URL keeps only its first word)."""
        if not self.clipboard.available:
            self.status = NO_CLIPBOARD
        elif not (text := (self.clipboard.get() or "").strip()):
            self.status = "The clipboard has no text"
        else:
            if self.focus == "url":
                self.draft += text.split()[0]
            else:
                self.title += " ".join(text.split())
            self.status = ""
        self.screen.redraw()

    def copy(self, index):
        if not self.clipboard.available:
            self.status = NO_CLIPBOARD
            self.screen.redraw()
            return False
        ok = self.clipboard.set(self.pinger.endpoints[index]["url"])
        self.status = "Copied!" if ok else "Could not copy"
        self.screen.redraw()
        return ok

    def click(self, hit, button, rect):
        kind = hit[0]
        if kind == "obs_row":
            if button == BTN_RIGHT:
                self.fx.scrap(rect)
                self.pinger.remove(hit[1])
                self.screen.overlay.hover = None
                self.screen.redraw()
            elif button == BTN_LEFT and self.copy(hit[1]):
                self.fx.pick(rect)
            return
        if button != BTN_LEFT:
            return
        if kind in ("obs_title_in", "obs_input"):
            self.focus = "title" if kind == "obs_title_in" else "url"
            self.screen.redraw()
            return
        self.screen.press(hit)
        if kind == "obs_add":
            self.add(rect)
        elif kind == "obs_paste":
            self.paste()
        elif kind == "obs_check":
            self.pinger.next_check = 0.0  # the main loop starts the round
            self.fx.pick(rect)
            self.screen.redraw()
        else:
            self.close()

    def key(self, key, ctrl):
        if key == KEY_ESC:
            self.close()
        elif key == KEY_TAB:
            self.focus = "url" if self.focus == "title" else "title"
            self.screen.redraw()
        elif key in ENTER:
            if self.focus == "title" and not self.draft.strip():
                self.focus = "url"
                self.screen.redraw()
            else:
                self.add(self.screen.rect("obs_add"))
        elif key == KEY_V and ctrl:
            self.paste()
        elif key == KEY_C and ctrl:
            hit = self.screen.under_mouse()
            if hit and hit[0] == "obs_row":
                self.copy(hit[1])
        elif key == KEY_BACKSPACE and getattr(self, self._field()):
            setattr(self, self._field(), erase(getattr(self, self._field()), word=ctrl))
            self.screen.redraw()
        return True

    def text(self, text):
        typed = printable(text)
        if self.focus == "url":
            typed = "".join(typed.split())  # URLs have no spaces
        if typed:
            setattr(self, self._field(), getattr(self, self._field()) + typed)
            self.screen.redraw()

    def scroll(self, steps):
        self.skip = clamp_skip(self.skip, steps, self.screen.overlay.obs_rows)
        self.screen.redraw()

    def payload(self):
        return {"open": self.is_open, "endpoints": self.pinger.endpoints, "draft": self.draft,
                "busy": self.pinger.busy, "title": self.title, "focus": self.focus, "status": self.status,
                "skip": self.skip, "checked": clock(self.pinger.checked_at)}
