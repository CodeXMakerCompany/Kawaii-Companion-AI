import datetime

from kawaii.alerts import ALERT_REPEAT, Alerts
from kawaii.features.reminders import Events


class FakeMonitor:
    def __init__(self, alarms=()):
        self.alarms = list(alarms)
        self.snoozed = []

    def snooze(self, name):
        self.snoozed.append(name)
        self.alarms = [a for a in self.alarms if a[0] != name]


TODAY = datetime.date(2026, 11, 25)


def test_due_reminders_first_then_alarms(tmp_path):
    events = Events(tmp_path / "events.json")
    events.add("2026-11-20", "Old one")
    events.add("2026-11-25", "Today one", yearly=True)
    events.items[-1]["since"] = "2026-01-01"  # made yearly before today's occurrence
    events.add("2026-12-01", "Later")
    alerts = Alerts(events, FakeMonitor([("cpu", "CPU is hot")]), today=lambda: TODAY)
    items = alerts.items()
    assert [i["title"] for i in items] == ["Old one", "Today one", "CPU is hot"]
    assert items[0]["label"] == "OVERDUE · FRI 20 NOV" and items[0]["action"] == "Done"
    assert items[1]["label"] == "REMINDER · TODAY · YEARLY"
    assert items[2] == {"id": "sys:cpu", "label": "SYSTEM ALARM", "title": "CPU is hot", "action": "Dismiss"}


def test_handle_marks_done_or_snoozes(tmp_path):
    events = Events(tmp_path / "events.json")
    events.add("2026-11-25", "Call mom")
    monitor = FakeMonitor([("ram", "RAM full")])
    alerts = Alerts(events, monitor, today=lambda: TODAY)
    alerts.handle("ev:" + events.items[0]["id"])
    alerts.handle("sys:ram")
    assert alerts.items() == []
    assert monitor.snoozed == ["ram"]


def test_new_alerts_nag_after_a_beat_then_every_few_minutes(tmp_path):
    events = Events(tmp_path / "events.json")
    alerts = Alerts(events, FakeMonitor(), today=lambda: TODAY)
    assert alerts.tick(0.0) == (False, False, False)
    events.add("2026-11-25", "Stretch")
    alerts.recheck()
    appeared, changed, nag = alerts.tick(1.0)
    assert appeared and changed and not nag
    assert alerts.due_count == 1
    assert alerts.tick(2.0)[2] is True
    assert alerts.tick(3.0)[2] is False
    assert alerts.tick(2.0 + ALERT_REPEAT)[2] is True


def test_checks_only_every_ten_seconds_unless_asked(tmp_path):
    events = Events(tmp_path / "events.json")
    alerts = Alerts(events, FakeMonitor(), today=lambda: TODAY)
    alerts.tick(0.0)
    events.add("2026-11-25", "Stretch")
    assert alerts.tick(5.0) == (False, False, False)
    assert alerts.tick(10.0)[0] is True


def test_nothing_waiting_stops_the_nagging(tmp_path):
    events = Events(tmp_path / "events.json")
    events.add("2026-11-25", "Stretch")
    alerts = Alerts(events, FakeMonitor(), today=lambda: TODAY)
    alerts.tick(0.0)
    alerts.handle("ev:" + events.items[0]["id"])
    alerts.tick(0.5)
    assert alerts.next_nag is None


def test_what_she_says(tmp_path):
    events = Events(tmp_path / "events.json")
    alerts = Alerts(events, FakeMonitor([("gpu_temp", "GPU hot")]), today=lambda: TODAY)
    assert alerts.announcement() == ("alarm", "gpu_temp")
    events.add("2026-11-20", "Taxes")
    assert alerts.announcement() == ("reminder_overdue", "Taxes")
    events.add("2026-11-25", "Today")
    assert alerts.announcement() == ("reminder_overdue", "Taxes")
    assert Alerts(Events(tmp_path / "none.json"), FakeMonitor(), today=lambda: TODAY).announcement() is None
