from kawaii.cards.base import Deck
from kawaii.cards.prs import PRCard
from kawaii.cards.settings import SettingsCard
from kawaii.input.keys import BTN_LEFT, KEY_ESC, KEY_R
from kawaii.settings import StateStore
from tests.fakes import make_screen


class FakePRs:
    def __init__(self):
        self.unread, self.checked_at, self.read = [{"id": 1}], None, 0

    def mark_read(self):
        self.read += 1
        self.unread = []


class FakeMover:
    monitors = [("DP-1", 2560, 1440), ("HDMI-1", 1920, 1080)]
    available = True

    def largest(self):
        return "DP-1"


def test_closing_the_comments_card_marks_them_read():
    screen = make_screen()
    card = PRCard(screen, FakePRs())
    deck = Deck(card)
    deck.click(("gh_badge", None), BTN_LEFT, (0, 0, 1, 1))
    assert card.is_open and card.prs.read == 0
    assert deck.key(KEY_ESC, False)
    assert card.prs.read == 1 and not card.is_open


def test_other_keys_pass_through_the_comments_card():
    deck = Deck(PRCard(make_screen(), FakePRs()))
    deck.show("prs")
    assert not deck.key(KEY_R, False)


def test_wheel_scrolls_the_comments():
    screen = make_screen()
    card = PRCard(screen, FakePRs())
    deck = Deck(card)
    deck.show("prs")
    screen.overlay.pr_rows = 5
    deck.scroll(-3, ("pr_card", None))
    assert card.skip == 3
    deck.scroll(-9, ("gh_badge", None))
    assert card.skip == 4
    deck.scroll(9, ("pr_card", None))
    assert card.skip == 0


def test_settings_pick_where_apps_open(tmp_path):
    store = StateStore(tmp_path / "s.json")
    card = SettingsCard(make_screen(), store, FakeMover(), here=lambda: "DP-1")
    deck = Deck(card)
    deck.show("settings")
    assert card.app_output() == "DP-1"  # auto: the largest
    deck.click(("set_mon", 2), BTN_LEFT, (0, 0, 1, 1))
    assert store.get("app_output") == "HDMI-1" and card.app_output() == "HDMI-1"
    deck.click(("set_mon", 9), BTN_LEFT, (0, 0, 1, 1))
    assert store.get("app_output") == "HDMI-1"
    deck.click(("set_done", None), BTN_LEFT, None)
    assert not card.is_open


def test_a_monitor_that_is_gone_falls_back_to_the_largest(tmp_path):
    store = StateStore(tmp_path / "s.json")
    store.set("app_output", "eDP-1")
    assert SettingsCard(make_screen(), store, FakeMover(), here=lambda: None).app_output() == "DP-1"
