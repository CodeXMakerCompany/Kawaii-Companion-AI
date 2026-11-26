"""Key and button codes (evdev: layout independent, like VTube Studio's hotkeys)."""

import json

BTN_LEFT, BTN_RIGHT = 0x110, 0x111

KEY_ESC, KEY_BACKSPACE, KEY_ENTER, KEY_KPENTER, KEY_R, KEY_F10 = 1, 14, 28, 96, 19, 68
KEY_C, KEY_V, KEY_TAB = 46, 47, 15
ENTER = (KEY_ENTER, KEY_KPENTER)
_KP = {1: 79, 2: 80, 3: 81, 4: 75, 5: 76, 6: 77, 7: 71, 8: 72, 9: 73, 0: 82}
_FKEYS = {1: 59, 2: 60, 3: 61, 4: 62, 5: 63, 6: 64, 7: 65, 8: 66, 9: 67, 10: 68, 11: 87, 12: 88}


def vtube_key_to_evdev(name):
    """VTube Studio trigger names -> evdev key codes ("Numpad1", "N1", "F1")."""
    if name.startswith("Numpad") and name[6:].isdigit():
        return _KP.get(int(name[6:]))
    if len(name) == 2 and name[0] == "N" and name[1].isdigit():
        return 11 if name[1] == "0" else 1 + int(name[1])
    if name[0] == "F" and name[1:].isdigit():
        return _FKEYS.get(int(name[1:]))
    return None


def load_hotkeys(path):
    """The model's hotkeys.json (written by tools/build_model.py) as {evdev key: expression}."""
    if not path.exists():
        return {}
    hotkeys = {}
    for trigger, exp in json.loads(path.read_text()).items():
        key = vtube_key_to_evdev(trigger)
        if key is not None:
            hotkeys[key] = exp
    return hotkeys
