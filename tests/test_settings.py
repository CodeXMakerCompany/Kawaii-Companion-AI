import json

from kawaii.settings import StateStore


def test_missing_or_broken_file_starts_empty(tmp_path):
    assert StateStore(tmp_path / "none.json").data == {"layouts": {}}
    bad = tmp_path / "bad.json"
    bad.write_text("{nope")
    assert StateStore(bad).data == {"layouts": {}}


def test_set_saves_right_away(tmp_path):
    path = tmp_path / "sub" / "state.json"
    store = StateStore(path)
    store.set("monitor_open", True)
    assert json.loads(path.read_text())["monitor_open"] is True
    assert StateStore(path).get("monitor_open") is True
    assert store.get("missing", 7) == 7


def test_layouts_are_per_monitor(tmp_path):
    path = tmp_path / "state.json"
    store = StateStore(path)
    store.remember_layout("DP-1", {"margin": [1, 2], "model_size": [400, 600]})
    again = StateStore(path)
    assert again.layout_for("DP-1")["margin"] == [1, 2]
    assert again.layout_for("HDMI-1") is None
    assert again.layout_for(None) is None
    assert again.get("output") == "DP-1"
