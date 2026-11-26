"""Transparent Live2D desktop overlay for Linux/Wayland (layer-shell + EGL + Cubism SDK via live2d-py).

Controls
  left-drag on her  move her around the desktop
  arrows            drag the arrows on each side of her (shown on hover) to resize; she scales to fit
  scroll            zoom the model inside her area (R fits her to it again)
  hover             the model looks at the cursor
  Pendings button   open today's pending list above her head (she raises her right hand)
                    type + Enter adds, click toggles done, right-click deletes, Esc closes
  Talk button       she talks for 10 seconds (click again to stop early)
  Dance button      she dances on a beat until clicked again
  Pose button       she strikes 5 photo poses in a row (click again to stop)
  Think button      finger on her chin, mulling it over (click again: she gets it)
  Huh? (mini)       a puzzled double take, the '?' popping up (click again to stop)
  Decode button     paste or type a JWT, timestamp, JSON, base64, URL, stack trace...: Decode shows
                    it readable, Copy copies it (Paste/Copy use wl-clipboard), Explain? sends a
                    stack trace to OpenRouter; Enter decodes, Ctrl+V pastes, Esc closes
  PR Review button  pick a repo under ~/Projects and a branch: Kiro opens on it with a new chat
                    asking to review that branch against main/master, typed in but not sent
  Settings (mini)   which monitor the apps she opens go to (largest by default); COSMIC only
  GitHub badge      new comments on your open pull requests (gh checks every 15 min): she says
                    what happened; click it to read them and see the repo (read only), Esc closes
  Kiro / Claude     while the app is open its icon floats by her head (Kiro right, Claude
                    left); while one of its agents works the icon's dots spin and she thinks
                    it over looking at it; when the last one is done she gets it. When one
                    waits on you (a permission, a question) its icon hops with a '?' and she
                    does 'huh?' double takes at it, turning to you
  Walk / Greet      she strolls side to side (until clicked again) / bows and waves hello
  Calendar button   pick a date, type a title, Add reminder; on the day she nags until Done
  top-right pill    CPU/GPU/RAM at a glance; click for the full monitor (alarms nag until dismissed)
  mic / Alt+F10     voice commands: start/stop listening (voice-toggle.sh for a global shortcut)
  hotkeys           same expression keys as VTube Studio (Numpad1-9, 1-0, F1-F4)
  Backspace         clear expressions
  R                 fit her whole body to her area
  Esc               quit (position, size and zoom are saved)

Resource choices
  - Frame-capped loop that sleeps on the Wayland socket: no busy-wait, no vsync spin.
  - No MSAA, no depth/stencil, and only her area is drawn.
  - Uses the downscaled texture from tools/build_model.py (2048px instead of 8192px).
  - The UI is painted once into a texture and only repainted when it changes.
  - Click effects (kawaii/render/fx.py) are drawn only while one plays, cropped to what they cover, at 60 fps;
    --no-fx, or the desktop's animations switch, turns them off.
  - Transparent pixels are left out of the input region, so clicks there reach the desktop.
"""

import argparse
from pathlib import Path

from kawaii.paths import MODEL


def parse_args(argv=None):
    ap = argparse.ArgumentParser(prog="viewer.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", type=Path, default=MODEL)
    ap.add_argument("--size", help="her area WxH on wide screens (default: last used, else 420x620)")
    ap.add_argument("--fps", type=float, default=30, help="frame cap (default 30)")
    ap.add_argument("--scale", type=float, help="fixed model zoom instead of fitting her to the area")
    ap.add_argument("--pendings", action="store_true", help="start with the Pendings list open")
    ap.add_argument("--no-fx", action="store_true",
                    help="no sakuga effects on clicks (also off when the desktop turns animations off)")
    ap.add_argument("--snapshot", type=Path, help="render ~2.5s, save a PNG with alpha and exit")
    ap.add_argument("--allow-multiple", action="store_true", help="keep other running copies instead of replacing them")
    return ap.parse_args(argv)
