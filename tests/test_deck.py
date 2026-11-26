"""The cards above her head: one open at a time, each handling its own clicks, keys and scrolling."""

from kawaii.cards.base import Card, Deck
from kawaii.input.keys import BTN_LEFT, BTN_RIGHT
from tests.fakes import make_screen


class Probe(Card):
    def __init__(self, screen, name, opener, open_fx="pop"):
        super().__init__(screen)
        self.name, self.opener, self.open_fx = name, opener, open_fx
        self.hits = (name + "_row",)
        self.scroll_hits = (name + "_card",)
        self.log = []

    def opened(self):
        self.log.append("opened")

    def closed(self):
        self.log.append("closed")

    def click(self, hit, button, rect):
        self.log.append(("click", hit, button))

    def key(self, key, ctrl):
        self.log.append(("key", key))
        return True

    def text(self, text):
        self.log.append(("text", text))

    def scroll(self, steps):
        self.log.append(("scroll", steps))


def make():
    screen = make_screen({("button", "a"): (0, 0, 100, 20), ("action", "b"): (0, 30, 100, 50)})
    a = Probe(screen, "a", ("button", "a"))
    b = Probe(screen, "b", ("action", "b"), open_fx="pick")
    return screen, a, b, Deck(a, b)


def test_one_card_at_a_time():
    _, a, b, deck = make()
    deck.show("a")
    deck.show("b")
    assert b.is_open and not a.is_open
    assert a.log == ["opened", "closed"]
    assert deck.current is b
    deck.show("b", False)
    assert deck.current is None


def test_closing_a_closed_card_does_nothing():
    _, a, _, deck = make()
    deck.show("a", False)
    assert a.log == []


def test_opener_toggles_with_a_pop_then_a_poof():
    screen, a, _, deck = make()
    assert deck.click(("button", "a"), BTN_LEFT, (0, 0, 100, 20))
    assert a.is_open
    screen.fx.pop.assert_called_once_with((0, 0, 100, 20))
    deck.click(("button", "a"), BTN_LEFT, (0, 0, 100, 20))
    assert not a.is_open
    screen.fx.poof.assert_called_once_with(84, 10)
    assert screen.dirty


def test_pick_style_opener_only_marks_opening():
    screen, _, b, deck = make()
    deck.click(("action", "b"), BTN_LEFT, (0, 30, 100, 50))
    deck.click(("action", "b"), BTN_LEFT, (0, 30, 100, 50))
    screen.fx.pick.assert_called_once()
    screen.fx.poof.assert_not_called()


def test_openers_ignore_right_clicks():
    _, a, _, deck = make()
    assert not deck.click(("button", "a"), BTN_RIGHT, None)
    assert not a.is_open


def test_card_hits_go_to_their_card():
    _, a, b, deck = make()
    assert deck.click(("b_row", 2), BTN_RIGHT, (1, 2, 3, 4))
    assert b.log == [("click", ("b_row", 2), BTN_RIGHT)]
    assert not deck.click(("other", None), BTN_LEFT, None)


def test_keys_text_and_wheel_go_to_the_open_card():
    _, a, _, deck = make()
    assert not deck.key(1, False)
    deck.show("a")
    assert deck.key(1, False)
    deck.text("x")
    assert deck.scroll(-1, ("a_card", None))
    assert not deck.scroll(-1, ("elsewhere", None))
    assert not deck.scroll(-1, None)
    assert a.log[1:] == [("key", 1), ("text", "x"), ("scroll", -1)]


def test_tick_reaches_every_card():
    _, a, b, deck = make()
    seen = []
    a.tick = lambda now: seen.append(("a", now))
    b.tick = lambda now: seen.append(("b", now))
    deck.tick(3.0)
    assert seen == [("a", 3.0), ("b", 3.0)]
