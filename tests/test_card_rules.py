from kawaii.cards.base import Deck
from kawaii.cards.rules import RulesCard
from kawaii.features.rules import Rulebook
from kawaii.input.keys import BTN_LEFT, BTN_RIGHT, KEY_C, KEY_ENTER, KEY_ESC, KEY_V
from tests.fakes import FakeClipboard, make_screen


def make(tmp_path, clip=None):
    screen = make_screen()
    card = RulesCard(screen, Rulebook(tmp_path / "rules.json"), clip or FakeClipboard())
    deck = Deck(card)
    deck.show("rules")
    return screen, card, deck


def test_enter_on_the_list_opens_the_typed_company(tmp_path):
    _, card, deck = make(tmp_path)
    deck.text("Acme")
    deck.key(KEY_ENTER, False)
    assert card.company == 0 and card.draft == ""
    assert card.rulebook.companies[0]["name"] == "Acme"


def test_enter_inside_a_company_adds_the_rule(tmp_path):
    _, card, deck = make(tmp_path)
    deck.text("Acme")
    deck.key(KEY_ENTER, False)
    deck.text("No deploys on Friday")
    deck.key(KEY_ENTER, False)
    assert [r["text"] for r in card.rulebook.companies[0]["rules"]] == ["No deploys on Friday"]
    assert card.skip is None  # scrolled to the new one


def test_empty_input_explains_itself(tmp_path):
    _, card, deck = make(tmp_path)
    deck.key(KEY_ENTER, False)
    assert card.status == "Type a company name first"
    card.rulebook.add_company("Acme")
    deck.click(("rules_row", 0), BTN_LEFT, (0, 0, 1, 1))
    deck.key(KEY_ENTER, False)
    assert card.status == "Write the rule first"


def test_esc_goes_back_then_closes(tmp_path):
    _, card, deck = make(tmp_path)
    card.rulebook.add_company("Acme")
    deck.click(("rules_row", 0), BTN_LEFT, (0, 0, 1, 1))
    deck.key(KEY_ESC, False)
    assert card.company is None and card.is_open
    deck.key(KEY_ESC, False)
    assert not card.is_open


def test_copy_one_rule_or_all_of_them(tmp_path):
    clip = FakeClipboard()
    screen, card, deck = make(tmp_path, clip)
    ci = card.rulebook.add_company("Acme")
    card.rulebook.add_rule(ci, "First")
    card.rulebook.add_rule(ci, "Second")
    card.company = ci
    screen.overlay.under = ("rules_row", 1)
    deck.key(KEY_C, True)
    assert clip.text == "Second"
    screen.overlay.under = None
    deck.key(KEY_C, True)
    assert clip.text == card.rulebook.as_text(ci)


def test_paste_flattens_whitespace(tmp_path):
    _, card, deck = make(tmp_path, FakeClipboard(" a\n  b "))
    deck.key(KEY_V, True)
    assert card.draft == "a b"


def test_paste_without_wl_clipboard(tmp_path):
    _, card, deck = make(tmp_path, FakeClipboard(available=False))
    deck.key(KEY_V, True)
    assert card.status == "Install wl-clipboard to copy and paste"


def test_right_click_removes_a_company_or_a_rule(tmp_path):
    _, card, deck = make(tmp_path)
    ci = card.rulebook.add_company("Acme")
    card.rulebook.add_rule(ci, "First")
    card.company = ci
    deck.click(("rules_row", 0), BTN_RIGHT, (0, 0, 1, 1))
    assert card.rulebook.companies[0]["rules"] == []
    card.company = None
    deck.click(("rules_row", 0), BTN_RIGHT, (0, 0, 1, 1))
    assert card.rulebook.companies == []
