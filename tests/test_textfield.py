from kawaii.input.textfield import erase, printable


def test_printable_drops_control_characters():
    assert printable("a\x16b\tc") == "abc"


def test_erase_one_character():
    assert erase("hello") == "hell"
    assert erase("") == ""


def test_erase_last_word():
    assert erase("hello big world", word=True) == "hello big"
    assert erase("hello world   ", word=True) == "hello"
    assert erase("single", word=True) == ""
