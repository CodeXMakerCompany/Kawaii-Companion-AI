import json

from kawaii.input import keys


def test_numpad_names_map_to_keypad_codes():
    assert keys.vtube_key_to_evdev("Numpad1") == 79
    assert keys.vtube_key_to_evdev("Numpad0") == 82


def test_number_row_names():
    assert keys.vtube_key_to_evdev("N1") == 2
    assert keys.vtube_key_to_evdev("N9") == 10
    assert keys.vtube_key_to_evdev("N0") == 11


def test_function_keys():
    assert keys.vtube_key_to_evdev("F1") == 59
    assert keys.vtube_key_to_evdev("F12") == 88


def test_unknown_names_are_ignored():
    assert keys.vtube_key_to_evdev("Space") is None
    assert keys.vtube_key_to_evdev("F13") is None


def test_load_hotkeys_skips_unknown_triggers(tmp_path):
    path = tmp_path / "hotkeys.json"
    path.write_text(json.dumps({"Numpad1": "chibi", "Space": "nope", "F2": "outfit"}))
    assert keys.load_hotkeys(path) == {79: "chibi", 60: "outfit"}


def test_load_hotkeys_without_a_file(tmp_path):
    assert keys.load_hotkeys(tmp_path / "missing.json") == {}
