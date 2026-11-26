"""Focus mode: a countdown (25 minutes, +5 at a time) during which she keeps quiet: no
spoken news, no greetings, no nagging. Instead a dropdown under the system pill counts
everything that is waiting, and when the time is up she tells you what came in.

The end time is saved, so a restart keeps the session going."""

import time

FOCUS_MINUTES = 25
EXTEND_MINUTES = 5
MAX_MINUTES = 180

# (count key, dropdown label, how she says it: singular, plural, whether it is news worth saying)
COUNTABLE = (
    ("agents_waiting", "Agents waiting on you", "agent waiting on you", "agents waiting on you", True),
    ("agents_working", "Agents working", "agent working", "agents working", False),
    ("pr_comments", "PR comments", "PR comment", "PR comments", True),
    ("reminders", "Reminders due", "reminder due", "reminders due", True),
    ("alarms", "System alarms", "system alarm", "system alarms", True),
    ("endpoints_down", "Endpoints down", "endpoint down", "endpoints down", True),
    ("pendings", "Pendings open", "pending open", "pendings open", False),
)


def summary_rows(counts):
    """[(label, count)] for the dropdown: every countable thing, in a fixed order."""
    return [(label, counts.get(key, 0)) for key, label, *_ in COUNTABLE]


def summary_sentence(counts):
    """What she says when focus ends: the things that need you, or that nothing came in."""
    parts = [f"{n} {one if n == 1 else many}" for key, _, one, many, news in COUNTABLE
             if news and (n := counts.get(key, 0))]
    if not parts:
        return "Nothing new came in."
    return (", ".join(parts[:-1]) + " and " + parts[-1] if len(parts) > 1 else parts[0]) + "."


class Focus:
    def __init__(self, store, now=time.time):
        self.store, self.now = store, now
        until = store.get("focus_until")
        self.until = until if until and until > now() else None
        self.open = False  # the dropdown is shown

    @property
    def on(self):
        return self.until is not None

    @property
    def quiet(self):
        """She doesn't speak up or come asking for attention."""
        return self.on

    def start(self, minutes=FOCUS_MINUTES):
        self._set(self.now() + min(minutes, MAX_MINUTES) * 60)

    def stop(self):
        self.open = False
        self._set(None)

    def toggle(self):
        self.stop() if self.on else self.start()

    def extend(self, minutes=EXTEND_MINUTES):
        if self.on:
            self._set(min(self.until + minutes * 60, self.now() + MAX_MINUTES * 60))

    def left(self):
        """Whole seconds left (rounded up), or None when off."""
        return max(0, int(self.until - self.now() + 0.999)) if self.on else None

    def label(self):
        left = self.left()
        if left is None:
            return None
        h, rest = divmod(left, 3600)
        m, s = divmod(rest, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

    def tick(self):
        """True once, when the time just ran out (focus is then off)."""
        if self.on and self.now() >= self.until:
            self.stop()
            return True
        return False

    def payload(self, counts):
        """For the switch and its dropdown; total counts only what needs you (the pill's badge)."""
        news = sum(counts.get(key, 0) for key, *_, is_news in COUNTABLE if is_news)
        return {"on": self.on, "label": self.label(), "open": self.open and self.on, "rows": summary_rows(counts),
                "total": news}

    def _set(self, until):
        self.until = until
        self.store.set("focus_until", until)
