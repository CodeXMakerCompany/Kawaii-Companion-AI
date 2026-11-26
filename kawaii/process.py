"""The viewer process and the desktop around it."""

import contextlib
import os
import signal
import subprocess
import time
from pathlib import Path

from kawaii.paths import APP_DIR


def replace_running_copy(timeout=4.0):
    """Ask any other running copy of this viewer to quit (it saves and exits cleanly on
    SIGTERM), so starting her again always gives exactly one, up-to-date, overlay."""
    me = os.getpid()
    others = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) == me:
            continue
        try:
            cmd = (entry / "cmdline").read_bytes().split(b"\0")
            same_app = any(arg.endswith(b"viewer.py") for arg in cmd) and Path(os.readlink(entry / "cwd")) == APP_DIR
        except OSError:
            continue
        if same_app and b"--snapshot" not in cmd and b"--allow-multiple" not in cmd:
            others.append(int(entry.name))
    for pid in others:
        with contextlib.suppress(OSError):
            os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + timeout
    while others and time.monotonic() < deadline:
        others = [pid for pid in others if Path(f"/proc/{pid}").exists()]
        time.sleep(0.05)
    for pid in others:  # an old build without the SIGTERM handler, or stuck
        with contextlib.suppress(OSError):
            os.kill(pid, signal.SIGKILL)


def animations_enabled():
    """The desktop's reduce-motion switch (GNOME's enable-animations); on when unknown."""
    try:
        out = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", "enable-animations"],
                             capture_output=True, text=True, timeout=2)
    except (OSError, subprocess.SubprocessError):
        return True
    return out.stdout.strip() != "false"
