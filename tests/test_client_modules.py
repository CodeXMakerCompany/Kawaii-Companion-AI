"""Switching client swaps each module's data and closes what was open."""

from kawaii.cards.base import Deck
from kawaii.cards.calendar import CalendarCard
from kawaii.cards.observe import ObserveCard
from kawaii.cards.pendings import PendingsCard
from kawaii.cards.rules import RulesCard
from kawaii.cards.vault import VaultCard
from kawaii.features.clients import Clients
from kawaii.features.observe import Pinger
from kawaii.features.pendings import Pendings
from kawaii.features.reminders import Events
from kawaii.features.rules import Rulebook
from kawaii.features.vault import Vault
from kawaii.input.keys import KEY_ESC
from tests.fakes import FakeClipboard, make_screen
from tests.test_card_calendar import FakeAlerts


def make(tmp_path):
    clients = Clients(tmp_path)
    clients.add("Acme")
    general = clients.space(clients.current)
    screen = make_screen()
    rulebook = Rulebook(tmp_path / "rules.json")
    cards = dict(
        pendings=PendingsCard(screen, Pendings(general.pendings), on_change=lambda: None),
        calendar=CalendarCard(screen, Events(general.events), FakeAlerts()),
        observe=ObserveCard(screen, Pinger(general.observe), FakeClipboard()),
        rules=RulesCard(screen, rulebook, FakeClipboard()),
        vault=VaultCard(screen, Vault(general.vault), FakeClipboard()),
    )
    deck = Deck(*cards.values(), client=lambda: clients.current)
    return clients, cards, deck


def test_every_client_module_is_marked(tmp_path):
    _, cards, _ = make(tmp_path)
    assert all(c.needs_client for c in cards.values())


def test_switching_swaps_the_data(tmp_path):
    clients, cards, deck = make(tmp_path)
    cards["pendings"].pendings.add("General thing")
    clients.select("Acme")
    deck.client_changed(clients.space("Acme"))
    assert cards["pendings"].pendings.items == []
    assert cards["pendings"].pendings.path == clients.space("Acme").pendings
    assert cards["calendar"].events.path == clients.space("Acme").events
    assert cards["observe"].pinger.state_file == clients.space("Acme").observe
    assert cards["vault"].vault.path == clients.space("Acme").vault
    clients.select("General")
    deck.client_changed(clients.space("General"))
    assert [i["text"] for i in cards["pendings"].pendings.items] == ["General thing"]


def test_switching_closes_the_open_card(tmp_path):
    clients, cards, deck = make(tmp_path)
    deck.show("vault")
    deck.client_changed(clients.space("Acme"))
    assert deck.current is None


def test_business_rules_open_straight_on_the_clients_rules(tmp_path):
    clients, cards, deck = make(tmp_path)
    clients.select("Acme")
    deck.client_changed(clients.space("Acme"))
    deck.show("rules")
    rules = cards["rules"]
    assert rules.company == rules.rulebook.find("Acme") is not None
    assert rules.payload()["locked"]
    deck.key(KEY_ESC, False)  # no list of companies to go back to: Esc closes
    assert not rules.is_open
