from kawaii.cards.base import Deck
from kawaii.cards.pendings import PendingsCard
from kawaii.features.pendings import Pendings
from kawaii.input.keys import BTN_LEFT, BTN_RIGHT, KEY_BACKSPACE, KEY_ENTER, KEY_ESC
from tests.fakes import make_screen


def make(tmp_path):
    screen = make_screen()
    changes = []
    card = PendingsCard(screen, Pendings(tmp_path / "p.json"), on_change=lambda: changes.append(1))
    deck = Deck(card)
    return screen, card, deck, changes


def test_typing_then_enter_adds_an_item(tmp_path):
    screen, card, deck, _ = make(tmp_path)
    deck.show("pendings")
    deck.text("buy milk")
    assert card.draft == "buy milk"
    deck.key(KEY_ENTER, False)
    assert [i["text"] for i in card.pendings.items] == ["buy milk"]
    assert card.draft == ""
    assert screen.after_paint  # the new row gets its effect once painted


def test_blank_enter_adds_nothing(tmp_path):
    _, card, deck, _ = make(tmp_path)
    deck.show("pendings")
    deck.text("   ")
    deck.key(KEY_ENTER, False)
    assert card.pendings.items == []


def test_backspace_and_ctrl_backspace(tmp_path):
    _, card, deck, _ = make(tmp_path)
    deck.show("pendings")
    deck.text("one two")
    deck.key(KEY_BACKSPACE, False)
    assert card.draft == "one tw"
    deck.key(KEY_BACKSPACE, True)
    assert card.draft == "one"


def test_click_toggles_and_right_click_deletes(tmp_path):
    screen, card, deck, _ = make(tmp_path)
    card.pendings.add("a")
    deck.click(("item", 0), BTN_LEFT, (10, 20, 200, 44))
    assert card.pendings.items[0]["done"]
    screen.fx.check.assert_called_once_with(31.5, 31.5)
    deck.click(("item", 0), BTN_RIGHT, (10, 20, 200, 44))
    assert card.pendings.items == []
    screen.fx.scrap.assert_called_once()


def test_open_and_close_move_her_hand(tmp_path):
    _, card, deck, changes = make(tmp_path)
    deck.show("pendings")
    deck.key(KEY_ESC, False)
    assert not card.is_open
    assert len(changes) == 2
