"""Desktop apps she shows by her head while they have a window, and which window a click raises."""

from kawaii.features.agents import IDLE, Claude, Kiro
from kawaii.features.apps import APPS, AppWatcher
from kawaii.features.icons import find_icon
from kawaii.wayland.winmove import pick_window


class FakeWindows:
    def __init__(self, app_ids=(), available=True):
        self.open_ids, self.available = set(app_ids), available

    def has_window(self, app_ids):
        return bool(self.open_ids & set(app_ids))


def by_name(name):
    return next(a for a in APPS if a.name == name)


def test_the_apps_she_watches():
    assert [a.name for a in APPS] == ["warp", "brave", "chrome", "firefox", "obsidian"]
    assert by_name("warp").app_ids == ("dev.warp.warp",)
    assert "brave-browser" in by_name("brave").app_ids
    assert "google-chrome" in by_name("chrome").app_ids
    assert "obsidian" in by_name("obsidian").app_ids


def test_open_while_it_has_a_window():
    warp = by_name("warp")(windows=FakeWindows({"dev.warp.warp"}))
    assert warp.poll(0.0) == (True, IDLE)
    warp.windows.open_ids.clear()
    assert warp.poll(0.5) == (True, IDLE)  # looks again only once a second
    assert warp.poll(1.0) == (False, IDLE)


def test_without_a_window_list_a_running_process_counts(monkeypatch):
    firefox = by_name("firefox")(windows=FakeWindows(available=False))
    monkeypatch.setattr(AppWatcher, "_running", lambda self, now: True)
    assert firefox.poll(0.0) == (True, IDLE)


def test_agent_apps_can_be_raised_too():
    assert "kiro" in Kiro.app_ids
    assert "com.anthropic.claude" in Claude.app_ids


def test_agent_apps_stay_open_without_a_window(monkeypatch):
    """Claude Code in a terminal has no Claude window, but its agent still works."""
    monkeypatch.setattr(AppWatcher, "_running", lambda self, now: True)
    claude = Claude(windows=FakeWindows())
    assert claude.poll(0.0)[0] is True


def test_find_icon_prefers_listed_files_then_the_theme(tmp_path):
    theme = tmp_path / "icons"
    (theme / "hicolor" / "128x128" / "apps").mkdir(parents=True)
    png = theme / "hicolor" / "128x128" / "apps" / "dev.warp.Warp.png"
    png.write_bytes(b"png")
    own = tmp_path / "own.png"
    assert find_icon((str(own),), ("dev.warp.Warp",), dirs=(theme,)) == str(png)
    own.write_bytes(b"png")
    assert find_icon((str(own),), ("dev.warp.Warp",), dirs=(theme,)) == str(own)
    assert find_icon((), ("nothing",), dirs=(theme,)) is None


def win(app, seen, active=False, last_active=0.0):
    return {"app": app, "seen": seen, "active": active, "last_active": last_active}


def test_pick_window_raises_the_one_used_last():
    a, b = win("brave-browser", 1, last_active=5), win("brave-browser", 2, last_active=9)
    assert pick_window([a, b], ("brave-browser",)) is b


def test_pick_window_cycles_when_one_is_already_in_front():
    a, b, c = win("x", 1, last_active=3), win("x", 2, active=True, last_active=9), win("x", 3, last_active=5)
    assert pick_window([a, b, c], ("x",)) is c
    c["active"], b["active"] = True, False
    assert pick_window([a, b, c], ("x",)) is a


def test_pick_window_matches_app_ids_exactly_and_ignores_case():
    assert pick_window([win("Dev.Warp.Warp", 1)], ("dev.warp.warp",))
    assert pick_window([win("brave-abcdef-Default", 1)], ("brave-browser",)) is None
    assert pick_window([], ("x",)) is None
