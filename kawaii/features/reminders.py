"""Dated reminders for the calendar card, saved as JSON."""

import datetime
import json
import uuid


class Events:
    """Dated reminders saved as JSON. A one-off is due from its date until marked done, so
    a missed day keeps reminding instead of silently passing.

    A yearly one comes back every year on its month/day: marking it done completes that
    year's occurrence. Occurrences before it was made yearly (`since`) never count, so
    adding an anniversary whose day already passed this year waits for next year.
    """

    def __init__(self, path):
        self.path = path
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            data = {}
        self.items = []
        for e in data.get("events", []):
            try:
                datetime.date.fromisoformat(e["date"])
                self.items.append({"id": str(e.get("id") or uuid.uuid4().hex), "date": e["date"],
                                   "title": str(e["title"]), "done": bool(e.get("done")),
                                   "yearly": bool(e.get("yearly")), "done_year": e.get("done_year"),
                                   "since": e.get("since") or datetime.date.today().isoformat()})
            except (KeyError, TypeError, ValueError):
                continue

    def save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"events": self.items}, ensure_ascii=False, indent=1))
        except OSError:
            pass

    def get(self, event_id):
        return next((e for e in self.items if e["id"] == event_id), None)

    @staticmethod
    def _on(year, base):
        """`base`'s month/day in `year` (29 Feb falls back to 28 Feb in common years)."""
        try:
            return base.replace(year=year)
        except ValueError:
            return base.replace(year=year, day=28)

    def when(self, e, today):
        """The date that matters now: a one-off's date; for a yearly one, this year's
        occurrence while it is waiting (upcoming or overdue), otherwise next year's."""
        base = datetime.date.fromisoformat(e["date"])
        if not e["yearly"]:
            return base
        occ = self._on(today.year, base)
        if (e["done_year"] or 0) >= today.year or occ.isoformat() < e["since"]:
            occ = self._on(today.year + 1, base)
        return occ

    def is_done(self, e):
        return e["done"] and not e["yearly"]

    def add(self, date, title, yearly=False):
        self.items.append({"id": uuid.uuid4().hex, "date": date, "title": title, "done": False, "yearly": yearly,
                           "done_year": None, "since": datetime.date.today().isoformat()})
        self.save()

    def update(self, event_id, date, title, yearly=None):
        e = self.get(event_id)
        if e:
            changed = date != e["date"] or (yearly is not None and yearly != e["yearly"])
            e.update(date=date, title=title)
            if yearly is not None:
                e["yearly"] = yearly
            if changed:  # a new date or rhythm starts fresh from today
                e.update(done=False, done_year=None, since=datetime.date.today().isoformat())
            self.save()

    def remove(self, event_id):
        self.items = [e for e in self.items if e["id"] != event_id]
        self.save()

    def toggle_done(self, event_id, today=None):
        """One-off: flip done. Yearly: complete the occurrence that is currently waiting."""
        e = self.get(event_id)
        if not e:
            return
        if e["yearly"]:
            e["done_year"] = self.when(e, today or datetime.date.today()).year
        else:
            e["done"] = not e["done"]
        self.save()

    def due(self, today):
        """Waiting today or earlier, oldest first."""
        due = [e for e in self.items if not self.is_done(e) and self.when(e, today) <= today]
        return sorted(due, key=lambda e: self.when(e, today))

    def listing(self, today):
        """Due first, then upcoming by date, then finished one-offs (most recent first)."""
        due = self.due(today)
        upcoming = sorted((e for e in self.items if not self.is_done(e) and self.when(e, today) > today),
                          key=lambda e: self.when(e, today))
        done = sorted((e for e in self.items if self.is_done(e)), key=lambda e: e["date"], reverse=True)
        return due + upcoming + done

    def marked_days(self, year):
        """ISO dates with a reminder still to do, around `year` (yearly ones on every year)."""
        days = set()
        for e in self.items:
            if self.is_done(e):
                continue
            if e["yearly"]:
                base = datetime.date.fromisoformat(e["date"])
                days.update(self._on(y, base).isoformat() for y in (year - 1, year, year + 1))
            else:
                days.add(e["date"])
        return days
