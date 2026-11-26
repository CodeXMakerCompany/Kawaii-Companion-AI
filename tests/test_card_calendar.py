import datetime

from kawaii.cards.base import Deck
from kawaii.cards.calendar import CalendarCard
from kawaii.features.reminders import Events
from kawaii.input.keys import BTN_LEFT, BTN_RIGHT, KEY_ENTER, KEY_ESC
from tests.fakes import make_screen

TODAY = datetime.date(2026, 11, 25)


class FakeAlerts:
    due_count = 0

    def __init__(self):
        self.rechecks = 0

    def recheck(self):
        self.rechecks += 1


def make(tmp_path):
    screen = make_screen({("cal_save", None): (0, 0, 50, 20)})
    alerts = FakeAlerts()
    card = CalendarCard(screen, Events(tmp_path / "e.json"), alerts, today=lambda: TODAY)
    return screen, card, Deck(card), alerts


def test_opens_on_today(tmp_path):
    _, card, deck, alerts = make(tmp_path)
    card.month, card.selected = (2020, 1), "2020-01-01"
    deck.show("calendar")
    assert card.month == (2026, 11) and card.selected == "2026-11-25"
    assert alerts.rechecks == 1


def test_month_arrows_wrap_years(tmp_path):
    _, card, deck, _ = make(tmp_path)
    deck.show("calendar")
    card.month = (2026, 12)
    deck.click(("cal_next", None), BTN_LEFT, None)
    assert card.month == (2027, 1)
    deck.click(("cal_prev", None), BTN_LEFT, None)
    deck.click(("cal_prev", None), BTN_LEFT, None)
    assert card.month == (2026, 11)


def test_clicking_a_greyed_day_jumps_to_its_month(tmp_path):
    _, card, deck, _ = make(tmp_path)
    deck.show("calendar")
    deck.click(("cal_day", "2026-12-02"), BTN_LEFT, (0, 0, 10, 10))
    assert card.selected == "2026-12-02" and card.month == (2026, 12)


def test_enter_saves_a_reminder_on_the_selected_day(tmp_path):
    screen, card, deck, alerts = make(tmp_path)
    deck.show("calendar")
    deck.click(("cal_yearly", None), BTN_LEFT, None)
    deck.text("Birthday")
    deck.key(KEY_ENTER, False)
    [e] = card.events.items
    assert (e["date"], e["title"], e["yearly"]) == ("2026-11-25", "Birthday", True)
    assert card.draft == "" and card.yearly is False
    screen.fx.tap.assert_called_once()


def test_editing_and_deleting(tmp_path):
    _, card, deck, _ = make(tmp_path)
    card.events.add("2026-12-24", "Gifts")
    event_id = card.events.items[0]["id"]
    deck.show("calendar")
    deck.click(("cal_event", event_id), BTN_LEFT, None)
    assert (card.editing, card.draft, card.month) == (event_id, "Gifts", (2026, 12))
    deck.text("!")
    deck.key(KEY_ENTER, False)
    assert card.events.items[0]["title"] == "Gifts!"
    deck.click(("cal_event", event_id), BTN_RIGHT, (0, 0, 10, 10))
    assert card.events.items == []


def test_reopening_while_editing_keeps_the_edited_day(tmp_path):
    _, card, deck, _ = make(tmp_path)
    card.events.add("2026-12-24", "Gifts")
    deck.show("calendar")
    deck.click(("cal_event", card.events.items[0]["id"]), BTN_LEFT, None)
    deck.key(KEY_ESC, False)
    deck.show("calendar")
    assert card.selected == "2026-12-24"


def test_payload_carries_what_the_overlay_draws(tmp_path):
    _, card, deck, _ = make(tmp_path)
    p = card.payload()
    assert set(p) == {"open", "month", "selected", "draft", "editing", "today", "events", "due_count", "yearly"}
