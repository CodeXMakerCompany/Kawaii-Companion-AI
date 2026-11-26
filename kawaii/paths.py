"""Where things live: the app folder, its bundled assets, and the per-user XDG folders."""

import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent  # commands.json and the scripts it names live here
ASSETS = APP_DIR / "assets"
MODEL = APP_DIR / "model" / "model.model3.json"

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "shark-viewer"
DATA_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "shark-viewer"
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "shark-viewer"

STATE_FILE = CONFIG_DIR / "state.json"
PENDINGS_FILE = CONFIG_DIR / "pendings.json"
EVENTS_FILE = CONFIG_DIR / "events.json"
