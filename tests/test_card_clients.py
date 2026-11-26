from kawaii.cards.base import Card, Deck
from kawaii.cards.clients import ClientsCard
from kawaii.features.clients import GENERAL, Clients
from kawaii.input.keys import BTN_LEFT, BTN_RIGHT, KEY_ENTER, KEY_ESC
from tests.fakes import make_screen


class Probe(Card):
    name, opener, needs_client = "pendings", ("button", "pendings"), True

    def __init__(self, screen):
        super().__init__(screen)
        self.spaces = []

    def client_changed(self, space):
        self.spaces.append(space)


def make(tmp_path):
    screen = make_screen()
    clients = Clients(tmp_path)
    switched = []
    card = ClientsCard(screen, clients, on_switch=lambda name: switched.append(name))
    probe = Probe(screen)
    deck = Deck(card, probe, client=lambda: clients.current)
    return screen, card, deck, switched, probe


def test_type_a_client_and_enter_adds_and_switches_to_it(tmp_path):
    _, card, deck, switched, _ = make(tmp_path)
    deck.show("clients")
    deck.text("Acme")
    deck.key(KEY_ENTER, False)
    assert card.clients.current == "Acme" and switched == ["Acme"]
    assert not card.is_open  # picked: back to work


def test_click_a_client_to_switch(tmp_path):
    _, card, deck, switched, _ = make(tmp_path)
    card.clients.add("Acme")
    deck.show("clients")
    deck.click(("client_row", 1), BTN_LEFT, (0, 0, 1, 1))
    assert card.clients.current == "Acme" and switched == ["Acme"]


def test_clicking_the_current_client_just_closes(tmp_path):
    _, card, deck, switched, _ = make(tmp_path)
    deck.show("clients")
    deck.click(("client_row", 0), BTN_LEFT, (0, 0, 1, 1))
    assert switched == [] and not card.is_open


def test_right_click_removes_but_never_the_current_one(tmp_path):
    _, card, deck, _, _ = make(tmp_path)
    card.clients.add("Acme")
    deck.show("clients")
    deck.click(("client_row", 0), BTN_RIGHT, (0, 0, 1, 1))
    assert GENERAL in card.clients.names and "Switch to another" in card.status
    deck.click(("client_row", 1), BTN_RIGHT, (0, 0, 1, 1))
    assert card.clients.names == [GENERAL] and "data is kept" in card.status


def test_payload_marks_the_current_client(tmp_path):
    _, card, _, _, _ = make(tmp_path)
    card.clients.add("Acme")
    p = card.payload()
    assert p["rows"] == [{"name": GENERAL, "current": True}, {"name": "Acme", "current": False}]
    assert p["current"] == GENERAL


def test_esc_closes(tmp_path):
    _, card, deck, _, _ = make(tmp_path)
    deck.show("clients")
    deck.key(KEY_ESC, False)
    assert not card.is_open


def test_cards_with_client_data_hear_about_a_switch(tmp_path):
    _, _, deck, _, probe = make(tmp_path)
    deck.client_changed("space")
    assert probe.spaces == ["space"]


def test_a_card_with_client_data_needs_a_client_first(tmp_path):
    screen, card, deck, _, probe = make(tmp_path)
    card.clients.current = None
    deck.click(("button", "pendings"), BTN_LEFT, (0, 0, 10, 10))
    assert not probe.is_open and card.is_open
    assert card.status == "Choose a client first"
