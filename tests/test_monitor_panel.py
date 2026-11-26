from kawaii.monitor_panel import MonitorPanel
from kawaii.settings import StateStore


class FakeMonitor:
    def __init__(self):
        self.shown = {"open": False, "rows": [], "cpu": 10}
        self.samples = []

    def due(self, now):
        return now >= 2 * len(self.samples)

    def sample(self, now, detail):
        self.samples.append((now, detail))

    def view(self, detail):
        return dict(self.shown, open=detail)


def test_repaints_only_when_the_numbers_change(tmp_path):
    panel = MonitorPanel(FakeMonitor(), StateStore(tmp_path / "s.json"))
    sampled, layout_changed = panel.tick(0.0)
    assert sampled and layout_changed and panel.dirty
    panel.dirty = False
    sampled, layout_changed = panel.tick(2.0)
    assert sampled and not layout_changed and not panel.dirty
    panel.monitor.shown["cpu"] = 50
    panel.tick(4.0)
    assert panel.dirty
    assert panel.tick(4.5) == (False, False)


def test_toggle_is_remembered(tmp_path):
    store = StateStore(tmp_path / "s.json")
    panel = MonitorPanel(FakeMonitor(), store)
    panel.toggle()
    assert panel.open and store.get("monitor_open") is True
    assert MonitorPanel(FakeMonitor(), StateStore(tmp_path / "s.json")).open
    panel.tick(0.0)
    assert panel.monitor.samples == [(0.0, True)]
