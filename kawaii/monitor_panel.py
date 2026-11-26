"""The CPU/GPU/RAM pill (top right) and the full system monitor it opens: a cheap sample
every 2s, repainted only when what it shows changed."""


class MonitorPanel:
    def __init__(self, monitor, store):
        self.monitor, self.store = monitor, store
        self.open = store.get("monitor_open", False)
        self.key = None  # last view, to repaint only on change
        self.shape = None  # what its click areas depend on (open, rows)
        self.dirty = True
        self.pos = (0, 0)

    def toggle(self):
        self.open = not self.open
        self.store.set("monitor_open", self.open)
        self.key = None

    def view(self):
        return self.monitor.view(self.open)

    def tick(self, now):
        """Returns (sampled, layout_changed): a sample was taken (alarms may have changed),
        and its click areas moved so the main layer must be repainted too."""
        if not self.monitor.due(now):
            return False, False
        self.monitor.sample(now, detail=self.open)
        mon = self.view()
        key = repr(mon)
        if key != self.key:
            self.key, self.dirty = key, True
        shape = (mon["open"], len(mon["rows"]), bool(mon.get("top"))) if mon else None
        layout_changed = shape != self.shape
        self.shape = shape
        return True, layout_changed
