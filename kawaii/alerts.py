"""Waiting bubbles: due reminders and system alarms. New ones are announced right away,
then she nags every few minutes until each is handled."""

import datetime

ALERT_REPEAT = 180  # seconds between her reminders while something is waiting
CHECK_EVERY = 10


class Alerts:
    def __init__(self, events, monitor, today=datetime.date.today):
        self.events, self.monitor, self.today = events, monitor, today
        self.ids = set()  # alerts already announced
        self.next_check = 0.0
        self.next_nag = None
        self.due_count = 0

    def items(self):
        """Due reminders first (oldest first), then system alarms."""
        today = self.today()
        out = []
        for e in self.events.due(today):
            day = self.events.when(e, today)
            label = "REMINDER · TODAY" if day == today else f"OVERDUE · {day.strftime('%a %d %b').upper()}"
            label += " · YEARLY" if e["yearly"] else ""
            out.append({"id": "ev:" + e["id"], "label": label, "title": e["title"], "action": "Done"})
        for name, message in self.monitor.alarms:
            out.append({"id": "sys:" + name, "label": "SYSTEM ALARM", "title": message, "action": "Dismiss"})
        return out

    def handle(self, alert_id):
        """Done on a reminder, Dismiss on an alarm."""
        kind, _, key = alert_id.partition(":")
        if kind == "ev":
            self.events.toggle_done(key)
        else:
            self.monitor.snooze(key)
        self.recheck()

    def recheck(self):
        self.next_check = 0.0

    def tick(self, now):
        """Returns (appeared, changed, nag): a new alert showed up, the bubbles changed, and
        whether to nag now."""
        appeared = changed = False
        if now >= self.next_check:
            self.next_check = now + CHECK_EVERY
            ids = {a["id"] for a in self.items()}
            appeared = bool(ids - self.ids)
            if appeared:
                self.next_nag = now + 1.0  # a beat after it appears
            if not ids:
                self.next_nag = None
            changed = ids != self.ids
            self.ids = ids
            self.due_count = len(self.events.due(self.today()))
        nag = bool(self.next_nag and now >= self.next_nag)
        if nag:
            self.next_nag = now + ALERT_REPEAT
        return appeared, changed, nag

    def announcement(self):
        """What she says about the first thing waiting: ("reminder_today" or
        "reminder_overdue", title), ("alarm", its kind), or None."""
        waiting = self.items()
        if not waiting:
            return None
        first = waiting[0]
        if first["id"].startswith("ev:"):
            return ("reminder_today" if first["label"].startswith("REMINDER") else "reminder_overdue"), first["title"]
        return "alarm", first["id"][4:].split(":")[0]
