"""Clients: who you are working for. Type a client, Enter adds it and switches to it; click
one to switch; right-click takes one off the list (its data is kept). Pendings, Calendar,
Observability, Business Rules and the Vault then show only that client's data."""

from kawaii.cards.base import Card, clamp_skip
from kawaii.input.keys import BTN_LEFT, BTN_RIGHT, ENTER, KEY_BACKSPACE, KEY_ESC
from kawaii.input.textfield import erase, printable


class ClientsCard(Card):
    name = "clients"
    opener = ("button", "client")
    open_fx = "pop"
    hits = ("client_row", "client_add", "client_done")
    scroll_hits = ("client_card", "client_row")

    def __init__(self, screen, clients, on_switch):
        super().__init__(screen)
        self.clients, self.on_switch = clients, on_switch  # on_switch(name): load that client's data
        self.draft = ""
        self.status = ""
        self.skip = 0

    def opened(self):
        self.draft, self.status, self.skip = "", "", 0

    def switch(self, name):
        if name != self.clients.current:
            self.clients.select(name)
            self.on_switch(name)
        self.close()

    def add(self, rect=None):
        name = self.clients.add(self.draft)
        if name is None:
            self.status = "Type a client name first"
            self.screen.redraw()
            return
        if rect:
            self.fx.done(rect)
        self.switch(name)

    def click(self, hit, button, rect):
        kind = hit[0]
        if kind == "client_row":
            if not 0 <= hit[1] < len(self.clients.names):
                return
            name = self.clients.names[hit[1]]
            if button == BTN_RIGHT:
                if self.clients.remove(name):
                    self.fx.scrap(rect)
                    self.status = f"Removed {name} from the list · its data is kept"
                    self.screen.overlay.hover = None
                else:
                    self.status = "Switch to another client first"
                self.screen.redraw()
            elif button == BTN_LEFT:
                self.fx.pick(rect)
                self.switch(name)
            return
        if button != BTN_LEFT:
            return
        self.screen.press(hit)
        self.add(rect) if kind == "client_add" else self.close()

    def key(self, key, ctrl):
        if key == KEY_ESC:
            self.close()
        elif key in ENTER:
            self.add(self.screen.rect("client_add"))
        elif key == KEY_BACKSPACE and self.draft:
            self.draft = erase(self.draft, word=ctrl)
            self.screen.redraw()
        return True

    def text(self, text):
        typed = printable(text)
        if typed:
            self.draft += typed
            self.screen.redraw()
            self.screen.caret_dust()

    def scroll(self, steps):
        self.skip = clamp_skip(self.skip, steps, self.screen.overlay.client_rows)
        self.screen.redraw()

    def payload(self):
        return {"open": self.is_open, "current": self.clients.current, "draft": self.draft, "status": self.status,
                "skip": self.skip, "rows": [{"name": n, "current": n == self.clients.current}
                                            for n in self.clients.names]}
