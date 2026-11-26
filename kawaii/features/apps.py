"""Desktop apps she shows by her head while they are open: Warp, the browsers, Obsidian.

An app counts as open while it has a window (COSMIC lists them, see wayland/winmove.py);
where windows can't be listed, while its process runs. Clicking its icon raises its window.
The agent apps (Kiro, Claude, in agents.py) build on this and also follow their logs."""

import os

from kawaii.features.icons import find_icon

IDLE = "idle"


class AppWatcher:
    name = ""
    app_ids = ()  # Wayland app ids of its windows, lowercase
    processes = ()  # /proc/<pid>/comm of the app's processes
    icons = ()  # icon files of the installed app; the first that exists is used
    icon_names = ()  # else these names in the icon theme (the .desktop Icon=)
    letter = "?"  # drawn on the icon when no icon file is found
    by_window = True  # open while it has a window (False: while its process runs)
    side = 1  # agents only: where its icon floats beside her head, 1 right, -1 left

    def __init__(self, windows=None, interval=1.0):
        self.windows = windows  # .available, .has_window(app_ids): the compositor's window list
        self.interval = interval
        self.next_check = 0.0
        self.open, self.state = False, IDLE
        self.pid = None
        self.next_scan = 0.0  # when to look through /proc again while the app is closed
        self.icon = find_icon(self.icons, self.icon_names)

    def poll(self, now):
        """Look again when due; returns (the app is open, IDLE)."""
        if now >= self.next_check:
            self.next_check = now + self.interval
            self.open = self._is_open(now)
        return self.open, self.state

    def _is_open(self, now):
        if self.by_window and self.windows and self.windows.available:
            return self.windows.has_window(self.app_ids)
        return self._running(now)

    def _running(self, now):
        if self.pid and self._is_app(self.pid):
            return True
        self.pid = None
        if now < self.next_scan:
            return False
        self.next_scan = now + 3.0  # closed: no need to read all of /proc every second
        self.pid = next((int(p) for p in os.listdir("/proc") if p.isdigit() and self._is_app(p)), None)
        return self.pid is not None

    def _is_app(self, pid):
        try:
            with open(f"/proc/{pid}/comm", "rb") as f:
                return f.read().strip() in self.processes
        except OSError:
            return False


class Warp(AppWatcher):
    name, letter = "warp", "W"
    app_ids = ("dev.warp.warp",)
    processes = (b"warp", b"warp-terminal")
    icon_names = ("dev.warp.Warp", "warp")


class Brave(AppWatcher):
    name, letter = "brave", "B"
    app_ids = ("brave-browser", "com.brave.browser")
    processes = (b"brave",)
    icon_names = ("brave-browser", "com.brave.Browser")


class Chrome(AppWatcher):
    name, letter = "chrome", "C"
    app_ids = ("google-chrome", "com.google.chrome")
    processes = (b"chrome",)
    icon_names = ("google-chrome", "com.google.Chrome")


class Firefox(AppWatcher):
    name, letter = "firefox", "F"
    app_ids = ("firefox", "org.mozilla.firefox")
    processes = (b"firefox", b"firefox-bin")
    icons = ("/usr/lib/firefox/browser/chrome/icons/default/default128.png",
             "/snap/firefox/current/default256.png")
    icon_names = ("firefox", "org.mozilla.firefox")


class Obsidian(AppWatcher):
    name, letter = "obsidian", "O"
    app_ids = ("obsidian", "md.obsidian.obsidian")
    processes = (b"obsidian",)
    icon_names = ("obsidian", "md.obsidian.Obsidian")


APPS = (Warp, Brave, Chrome, Firefox, Obsidian)
