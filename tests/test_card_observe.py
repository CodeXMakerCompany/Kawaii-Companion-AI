from kawaii.cards.base import Deck
from kawaii.cards.observe import ObserveCard
from kawaii.input.keys import BTN_LEFT, BTN_RIGHT, KEY_BACKSPACE, KEY_C, KEY_ENTER, KEY_TAB, KEY_V
from tests.fakes import FakeClipboard, make_screen


class FakePinger:
    def __init__(self):
        self.endpoints, self.busy, self.checked_at, self.next_check = [], False, None, 99.0

    def add(self, url, title=""):
        if any(e["url"] == url for e in self.endpoints):
            return False
        self.endpoints.append({"url": url, "title": title})
        return True

    def remove(self, index):
        del self.endpoints[index]


def make(clip=None):
    screen = make_screen({("obs_add", None): (0, 0, 10, 10)})
    card = ObserveCard(screen, FakePinger(), clip or FakeClipboard())
    deck = Deck(card)
    deck.show("observe")
    return screen, card, deck


def test_enter_on_title_moves_to_url_then_adds():
    screen, card, deck = make()
    deck.text("API")
    deck.key(KEY_ENTER, False)
    assert card.focus == "url"
    deck.text("https://x.dev/health")
    deck.key(KEY_ENTER, False)
    assert card.pinger.endpoints == [{"url": "https://x.dev/health", "title": "API"}]
    assert (card.draft, card.title, card.focus) == ("", "", "title")
    screen.fx.done.assert_called_once()


def test_urls_have_no_spaces():
    _, card, deck = make()
    deck.key(KEY_TAB, False)
    deck.text("https://a b.dev")
    assert card.draft == "https://ab.dev"


def test_duplicate_urls_are_refused():
    _, card, deck = make()
    card.pinger.add("https://a.dev")
    card.draft = "https://a.dev"
    deck.click(("obs_add", None), BTN_LEFT, (0, 0, 10, 10))
    assert card.status == "That URL is already watched"


def test_add_without_url_asks_for_it():
    _, card, deck = make()
    deck.click(("obs_add", None), BTN_LEFT, (0, 0, 10, 10))
    assert card.focus == "url" and card.status == "Type the URL too"


def test_paste_into_the_focused_field():
    _, card, deck = make(FakeClipboard("  https://p.dev/x  and more "))
    deck.key(KEY_V, True)
    assert card.title == "https://p.dev/x and more"
    deck.click(("obs_input", None), BTN_LEFT, None)
    deck.key(KEY_V, True)
    assert card.draft == "https://p.dev/x"


def test_copy_the_endpoint_under_the_pointer():
    clip = FakeClipboard()
    screen, card, deck = make(clip)
    card.pinger.add("https://a.dev")
    screen.overlay.under = ("obs_row", 0)
    deck.key(KEY_C, True)
    assert clip.text == "https://a.dev" and card.status == "Copied!"


def test_right_click_removes_and_check_now_starts_a_round():
    screen, card, deck = make()
    card.pinger.add("https://a.dev")
    deck.click(("obs_row", 0), BTN_RIGHT, (0, 0, 1, 1))
    assert card.pinger.endpoints == []
    deck.click(("obs_check", None), BTN_LEFT, (0, 0, 1, 1))
    assert card.pinger.next_check == 0.0


def test_ctrl_backspace_erases_a_word_in_the_focused_field():
    _, card, deck = make()
    deck.text("my api")
    deck.key(KEY_BACKSPACE, True)
    assert card.title == "my"


def test_reopening_starts_on_the_title_field():
    _, card, deck = make()
    deck.key(KEY_TAB, False)
    card.status = "x"
    deck.show("observe", False)
    deck.show("observe")
    assert (card.focus, card.status, card.skip) == ("title", "", 0)
