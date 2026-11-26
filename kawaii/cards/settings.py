"""Settings: which monitor the apps she opens go to (largest by default); COSMIC only."""

from kawaii.cards.base import Card
from kawaii.input.keys import BTN_LEFT, KEY_ESC


class SettingsCard(Card):
    name = "settings"
    opener = ("action", "settings")
    hits = ("set_mon", "set_done")

    def __init__(self, screen, store, mover, here):
        super().__init__(screen)
        self.store, self.mover, self.here = store, mover, here  # here(): the monitor she is on

    def app_output(self):
        """The monitor apps she opens should land on: your choice, or the largest one."""
        choice = self.store.get("app_output", "auto")
        return choice if choice in [m[0] for m in self.mover.monitors] else self.mover.largest()

    def click(self, hit, button, rect):
        if button != BTN_LEFT:
            return
        if hit[0] == "set_done":
            self.close()
            return
        choices = ["auto"] + [m[0] for m in self.mover.monitors]
        if hit[1] < len(choices):
            self.store.set("app_output", choices[hit[1]])
            self.fx.pick(rect)
            self.screen.redraw()

    def key(self, key, ctrl):
        if key == KEY_ESC:
            self.close()
            return True
        return False

    def payload(self):
        return {"open": self.is_open, "monitors": self.mover.monitors, "choice": self.store.get("app_output", "auto"),
                "largest": self.mover.largest(), "available": self.mover.available, "here": self.here()}
