"""Pendings: today's to-do list above her head (she raises her hand while it is open).
Type + Enter adds, click toggles done, right-click deletes, Esc closes."""

from kawaii.cards.base import Card
from kawaii.features.pendings import Pendings
from kawaii.input.keys import BTN_LEFT, BTN_RIGHT, ENTER, KEY_BACKSPACE, KEY_ESC
from kawaii.input.textfield import erase


class PendingsCard(Card):
    name = "pendings"
    opener = ("button", "pendings")
    open_fx = "pop"
    hits = ("item",)
    needs_client = True

    def __init__(self, screen, pendings, on_change):
        super().__init__(screen)
        self.pendings = pendings
        self.on_change = on_change  # her hand moves, so her outline changes
        self.draft = ""

    def client_changed(self, space):
        self.pendings, self.draft = Pendings(space.pendings), ""

    def opened(self):
        self.pendings.roll_day()
        self.on_change()

    def closed(self):
        self.on_change()

    def click(self, hit, button, rect):
        index = hit[1]
        box = (rect[0] + 21.5, rect[1] + 11.5)  # its checkbox
        if button == BTN_LEFT:
            self.pendings.toggle(index)
            self.fx.check(*box) if self.pendings.items[index]["done"] else self.fx.poof(*box)
        elif button == BTN_RIGHT:
            self.fx.scrap(rect)
            self.pendings.remove(index)
            self.screen.overlay.hover = None
        self.screen.redraw()

    def key(self, key, ctrl):  # typing into the list: no hotkeys, Esc just closes it
        if key == KEY_ESC:
            self.close()
        elif key in ENTER:
            text = self.draft.strip()
            if text:
                self.pendings.add(text)
                new = len(self.pendings.items) - 1
                self.screen.after(lambda: self.screen.rect("item", new) and self.fx.done(self.screen.rect("item", new)))
            self.draft = ""
            self.screen.redraw()
        elif key == KEY_BACKSPACE and self.draft:
            self.draft = erase(self.draft, word=ctrl)
            self.screen.redraw()
        return True

    def text(self, text):
        self.draft += text
        self.screen.redraw()
        self.screen.caret_dust()

    def payload(self):
        return {"open": self.is_open, "pendings": self.pendings, "draft": self.draft}
