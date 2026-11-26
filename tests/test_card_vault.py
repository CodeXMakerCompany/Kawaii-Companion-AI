from kawaii.cards.base import Deck
from kawaii.cards.vault import CLEAR_AFTER, VaultCard
from kawaii.features.vault import Vault
from kawaii.input.keys import BTN_LEFT, BTN_RIGHT, KEY_BACKSPACE, KEY_ENTER, KEY_ESC, KEY_TAB, KEY_V
from tests.fakes import FakeClipboard, make_screen
from tests.test_vault import Clock

SECRET = "sk-proj-1234567890abcdef"


def make(tmp_path, clip=None):
    screen = make_screen({("vault_add", None): (0, 0, 10, 10)})
    card = VaultCard(screen, Vault(tmp_path / "vault.txt", now=Clock()), clip or FakeClipboard())
    deck = Deck(card)
    deck.show("vault")
    return screen, card, deck


def open_reason(deck, name="OpenAI"):
    deck.text(name)
    deck.key(KEY_ENTER, False)


def add_key(deck, name="dev", secret=SECRET):
    deck.text(name)
    deck.key(KEY_ENTER, False)  # from Name to Key
    deck.text(secret)
    deck.key(KEY_ENTER, False)


def test_reason_first_then_its_keys(tmp_path):
    _, card, deck = make(tmp_path)
    open_reason(deck)
    assert card.reason == 0 and card.focus == "name"
    add_key(deck)
    assert card.vault.reasons[0]["keys"][0]["secret"] == SECRET
    assert (card.key_name, card.secret, card.focus) == ("", "", "name")


def test_the_screen_never_gets_the_secret(tmp_path):
    _, card, deck = make(tmp_path)
    open_reason(deck)
    deck.text("dev")
    deck.key(KEY_TAB, False)
    deck.text(SECRET)  # still typing it
    assert SECRET not in repr(card.payload())
    deck.key(KEY_ENTER, False)
    payload = repr(card.payload())
    assert SECRET not in payload and "sk-p…cdef" in payload


def test_click_copies_the_key_then_clears_the_clipboard(tmp_path):
    clip = FakeClipboard()
    screen, card, deck = make(tmp_path, clip)
    open_reason(deck)
    add_key(deck)
    deck.click(("vault_row", 0), BTN_LEFT, (0, 0, 1, 1))
    assert clip.text == SECRET and "Copied" in card.status
    deck.tick(1.0)  # the copy's clock starts at the first frame after it
    deck.tick(1.0 + CLEAR_AFTER - 1)
    assert clip.text == SECRET
    deck.tick(1.0 + CLEAR_AFTER + 1)
    assert clip.text == "" and card.status == "Clipboard cleared"


def test_a_clipboard_you_changed_since_is_left_alone(tmp_path):
    clip = FakeClipboard()
    _, card, deck = make(tmp_path, clip)
    open_reason(deck)
    add_key(deck)
    deck.click(("vault_row", 0), BTN_LEFT, (0, 0, 1, 1))
    deck.tick(0.0)
    clip.text = "something else"
    deck.tick(CLEAR_AFTER + 1)
    assert clip.text == "something else"


def test_temporary_switch(tmp_path):
    _, card, deck = make(tmp_path)
    open_reason(deck)
    deck.click(("vault_temp", None), BTN_LEFT, (0, 0, 1, 1))
    add_key(deck)
    assert card.vault.reasons[0]["keys"][0]["expires"] is not None
    assert card.temporary is False  # one key at a time


def test_paste_goes_into_the_focused_field(tmp_path):
    _, card, deck = make(tmp_path, FakeClipboard("  " + SECRET + "\n"))
    open_reason(deck)
    deck.key(KEY_TAB, False)
    deck.key(KEY_V, True)
    assert card.secret == SECRET


def test_add_without_a_key_asks_for_it(tmp_path):
    _, card, deck = make(tmp_path)
    open_reason(deck)
    deck.text("dev")
    deck.click(("vault_add", None), BTN_LEFT, (0, 0, 10, 10))
    assert card.focus == "secret" and card.status == "Paste or type the key too"


def test_backspace_edits_the_focused_field(tmp_path):
    _, card, deck = make(tmp_path)
    open_reason(deck)
    deck.key(KEY_TAB, False)
    deck.text("abc")
    deck.key(KEY_BACKSPACE, False)
    assert card.secret == "ab"


def test_esc_goes_back_then_closes_and_forgets_drafts(tmp_path):
    _, card, deck = make(tmp_path)
    open_reason(deck)
    deck.key(KEY_TAB, False)
    deck.text("half typed")
    deck.key(KEY_ESC, False)
    assert card.reason is None and card.secret == "" and card.is_open
    deck.key(KEY_ESC, False)
    assert not card.is_open


def test_right_click_removes(tmp_path):
    _, card, deck = make(tmp_path)
    open_reason(deck)
    add_key(deck)
    deck.click(("vault_row", 0), BTN_RIGHT, (0, 0, 1, 1))
    assert card.vault.reasons[0]["keys"] == []
    deck.key(KEY_ESC, False)
    deck.click(("vault_row", 0), BTN_RIGHT, (0, 0, 1, 1))
    assert card.vault.reasons == []


def test_clicking_a_reason_opens_it(tmp_path):
    _, card, deck = make(tmp_path)
    card.vault.add_reason("AWS")
    deck.click(("vault_row", 0), BTN_LEFT, (0, 0, 1, 1))
    assert card.reason == 0
