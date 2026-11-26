from types import SimpleNamespace

from kawaii.body.body import Body
from kawaii.cards.base import Deck
from kawaii.cards.decoder import DecoderCard
from kawaii.input.keys import BTN_LEFT, KEY_C, KEY_ENTER, KEY_ESC, KEY_V
from tests.fakes import FakeClipboard, make_screen


class FakeExplainer:
    def __init__(self):
        self.busy, self.asked, self.answer = False, None, None

    def start(self, text):
        self.busy, self.asked = True, text

    def poll(self):
        answer, self.answer = self.answer, None
        return answer


def fake_decode(text):
    return SimpleNamespace(kind="JSON", copy=text.upper()) if text.strip().startswith("{") else None


def make(clip=None):
    screen = make_screen({("dec_run", None): (0, 0, 10, 10), ("dec_copy", None): (20, 0, 30, 10)})
    body = Body()
    card = DecoderCard(screen, clip or FakeClipboard(), FakeExplainer(), body, head=lambda: (5, 5), decode=fake_decode)
    deck = Deck(card)
    deck.show("decoder")
    return screen, card, deck, body


def test_enter_decodes_the_draft():
    screen, card, deck, _ = make()
    deck.text('{"a":1}')
    deck.key(KEY_ENTER, False)
    assert card.result.kind == "JSON" and card.status == ""
    screen.fx.done.assert_called_once()


def test_nothing_to_decode():
    _, card, deck, _ = make()
    deck.text("hello")
    deck.key(KEY_ENTER, False)
    assert card.result is None and card.status == "Nothing to decode"


def test_paste_decodes_right_away():
    _, card, deck, _ = make(FakeClipboard('{"b":2}'))
    deck.key(KEY_V, True)
    assert card.draft == '{"b":2}' and card.result is not None


def test_paste_without_wl_clipboard():
    _, card, deck, _ = make(FakeClipboard(available=False))
    deck.key(KEY_V, True)
    assert card.status == "Install wl-clipboard to paste"


def test_copy_prefers_the_explanation():
    clip = FakeClipboard()
    _, card, deck, _ = make(clip)
    deck.text("{x}")
    deck.key(KEY_ENTER, False)
    deck.key(KEY_C, True)
    assert clip.text == "{X}" and card.status == "Copied!"
    card.explanation = "because"
    deck.click(("dec_copy", None), BTN_LEFT, (20, 0, 30, 10))
    assert clip.text == "because"


def test_clear_resets_the_card():
    _, card, deck, _ = make()
    deck.text("{x}")
    deck.key(KEY_ENTER, False)
    deck.click(("dec_clear", None), BTN_LEFT, None)
    assert (card.draft, card.result, card.status) == ("", None, "")


def test_explain_thinks_until_the_answer_comes():
    screen, card, deck, body = make()
    deck.text("Traceback ...")
    deck.click(("dec_explain", None), BTN_LEFT, None)
    assert card.explainer.asked == "Traceback ..." and card.status == "Asking OpenRouter…"
    assert body.thinker.active
    card.explainer.answer = ("It broke", None)
    deck.tick(1.0)
    assert card.explanation == "It broke" and card.status == ""
    assert not body.thinker.active
    screen.fx.later.assert_called_once()


def test_failed_explanation_says_why():
    _, card, deck, _ = make()
    card.explainer.answer = (None, "no key")
    deck.tick(1.0)
    assert card.status == "No explanation: no key"


def test_esc_closes():
    _, card, deck, _ = make()
    deck.key(KEY_ESC, False)
    assert not card.is_open
