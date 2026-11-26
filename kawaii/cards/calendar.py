"""Calendar: pick a date, type a title, Add reminder (Yearly to repeat it); on the day she
nags until Done. Clicking a reminder edits it, right-click deletes it."""

import datetime

from kawaii.cards.base import Card, middle
from kawaii.input.keys import BTN_LEFT, BTN_RIGHT, ENTER, KEY_BACKSPACE, KEY_ESC
from kawaii.input.textfield import erase


class CalendarCard(Card):
    name = "calendar"
    opener = ("button", "calendar")
    open_fx = "pop"
    hits = ("cal_prev", "cal_next", "cal_day", "cal_save", "cal_new", "cal_yearly", "cal_delete", "cal_done",
            "cal_event")

    def __init__(self, screen, events, alerts, today=datetime.date.today):
        super().__init__(screen)
        self.events, self.alerts, self.today = events, alerts, today
        day = today()
        self.month = (day.year, day.month)
        self.selected = day.isoformat()
        self.draft = ""
        self.editing = None  # id of the reminder being edited
        self.yearly = False  # Yearly switch for the reminder being added/edited

    def opened(self):
        if not self.editing:
            day = self.today()
            self.month, self.selected = (day.year, day.month), day.isoformat()
        self.alerts.recheck()

    def closed(self):
        self.alerts.recheck()

    def save(self):
        title = self.draft.strip()
        if not title:
            return
        if self.editing:
            self.events.update(self.editing, self.selected, title, self.yearly)
        else:
            self.events.add(self.selected, title, self.yearly)
        self.draft, self.editing, self.yearly = "", None, False
        self.screen.redraw()
        self.alerts.recheck()

    def edit(self, event_id):
        e = self.events.get(event_id)
        if e:
            day = datetime.date.fromisoformat(e["date"])
            self.editing, self.selected, self.month = event_id, e["date"], (day.year, day.month)
            self.draft, self.yearly = e["title"], e["yearly"]
            self.screen.redraw()

    def _forget_editing(self):
        self.editing, self.draft, self.yearly = None, "", False

    def click(self, hit, button, rect):
        kind = hit[0]
        if kind == "cal_event":
            if button == BTN_LEFT:
                self.edit(hit[1])
            elif button == BTN_RIGHT:
                self.fx.scrap(rect)
                self.events.remove(hit[1])
                if self.editing == hit[1]:
                    self.editing, self.draft = None, ""
                self.screen.overlay.hover = None
                self.screen.redraw()
                self.alerts.recheck()
            return
        if button != BTN_LEFT:
            return
        if kind in ("cal_prev", "cal_next"):
            y, m = self.month
            m += -1 if kind == "cal_prev" else 1
            self.month = (y + (m - 1) // 12, (m - 1) % 12 + 1)
        elif kind == "cal_day":
            self.selected = hit[1]
            day = datetime.date.fromisoformat(hit[1])
            self.month = (day.year, day.month)  # clicking a greyed day jumps to its month
            self.fx.pick(rect)
        elif kind == "cal_save":
            if self.draft.strip():
                self.fx.tap(rect)
            self.save()
        elif kind == "cal_new":
            self._forget_editing()
        elif kind == "cal_yearly":
            self.yearly = not self.yearly
        elif kind == "cal_delete":
            self.fx.scrap(rect)
            self.events.remove(self.editing)
            self._forget_editing()
            self.alerts.recheck()
        elif kind == "cal_done":
            self.events.toggle_done(hit[1])
            self.alerts.recheck()
            cx, cy = middle(rect)
            self.fx.check(cx, cy) if self.events.is_done(self.events.get(hit[1])) else self.fx.poof(cx, cy)
        self.screen.redraw()

    def key(self, key, ctrl):  # typing a reminder title: Enter saves, Esc closes
        if key == KEY_ESC:
            self.close()
        elif key in ENTER:
            if self.draft.strip() and self.screen.rect("cal_save"):
                self.fx.tap(self.screen.rect("cal_save"))
            self.save()
        elif key == KEY_BACKSPACE and self.draft:
            self.draft = erase(self.draft, word=ctrl)
            self.screen.redraw()
        return True

    def text(self, text):
        self.draft += text
        self.screen.redraw()
        self.screen.caret_dust()

    def payload(self):
        return {"open": self.is_open, "month": self.month, "selected": self.selected, "draft": self.draft,
                "editing": self.editing, "today": self.today(), "events": self.events,
                "due_count": self.alerts.due_count, "yearly": self.yearly}
