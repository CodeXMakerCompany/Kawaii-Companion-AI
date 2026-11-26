"""Finding an installed app's icon as a PNG file (the effects load it with Pillow, so no SVG)."""

import os
from pathlib import Path

ICON_DIRS = (Path.home() / ".local/share/icons", Path("/usr/share/icons"),
             Path.home() / ".local/share/flatpak/exports/share/icons", Path("/var/lib/flatpak/exports/share/icons"))
SIZES = ("256x256", "512x512", "128x128", "96x96", "64x64", "48x48")


def find_icon(files=(), names=(), dirs=ICON_DIRS):
    """The first of `files` that exists, else the biggest hicolor PNG named one of `names`
    (an app's .desktop Icon=), else /usr/share/pixmaps; None when there is none."""
    for f in files:
        if os.path.exists(f):
            return str(f)
    for name in names:
        for base in dirs:
            for size in SIZES:
                path = Path(base) / "hicolor" / size / "apps" / f"{name}.png"
                if path.exists():
                    return str(path)
        pixmap = Path("/usr/share/pixmaps") / f"{name}.png"
        if dirs is ICON_DIRS and pixmap.exists():
            return str(pixmap)
    return None
