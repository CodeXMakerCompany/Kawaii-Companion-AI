"""Clients: who you are working for. Each client gets its own pendings, reminders,
endpoints, business rules and vault; picking one shows only that client's data."""

import json

from kawaii.features.clients import GENERAL, Clients, slug


def make(tmp_path):
    return Clients(tmp_path)


def test_a_fresh_install_starts_with_general(tmp_path):
    clients = make(tmp_path)
    assert clients.names == [GENERAL] and clients.current == GENERAL


def test_add_select_and_remember(tmp_path):
    clients = make(tmp_path)
    assert clients.add("  Acme   Corp ") == "Acme Corp"
    assert clients.add("acme corp") == "Acme Corp"  # the same client, any case
    assert clients.add("") is None
    clients.select("Acme Corp")
    again = make(tmp_path)
    assert again.names == [GENERAL, "Acme Corp"] and again.current == "Acme Corp"


def test_the_client_you_are_in_cannot_be_removed(tmp_path):
    clients = make(tmp_path)
    clients.add("Acme")
    assert clients.remove(GENERAL) is False
    clients.select("Acme")
    assert clients.remove(GENERAL) is True
    assert clients.names == ["Acme"]


def test_removing_keeps_the_data(tmp_path):
    clients = make(tmp_path)
    clients.add("Acme")
    space = clients.space("Acme")
    space.folder.mkdir(parents=True)
    (space.folder / "pendings.json").write_text("{}")
    clients.remove("Acme")
    assert (space.folder / "pendings.json").exists()
    clients.add("Acme")  # adding it back brings its data back
    assert clients.space("Acme").folder == space.folder


def test_each_client_has_its_own_files(tmp_path):
    clients = make(tmp_path)
    clients.add("Acme Corp")
    s = clients.space("Acme Corp")
    assert s.folder == tmp_path / "clients" / "acme-corp"
    assert (s.pendings, s.events, s.observe, s.vault) == (
        s.folder / "pendings.json", s.folder / "events.json", s.folder / "observe.json", s.folder / "vault.txt")


def test_slugs_are_safe_folder_names():
    assert slug("Acme Corp") == "acme-corp"
    assert slug("../etc/passwd") == "etc-passwd"
    assert slug("Café Ñandú") == "cafe-nandu"
    assert slug("!!!") == "client"


def test_existing_data_moves_into_general_once(tmp_path):
    (tmp_path / "pendings.json").write_text('{"items": [{"text": "a"}]}')
    (tmp_path / "events.json").write_text('{"events": []}')
    (tmp_path / "vault.txt").write_text("secret line\n")
    (tmp_path / "rules.json").write_text(json.dumps({"companies": [{"name": "Assistance Connect", "rules": []}]}))
    clients = make(tmp_path)
    general = clients.space(GENERAL)
    assert json.loads(general.pendings.read_text())["items"][0]["text"] == "a"
    assert general.vault.read_text() == "secret line\n"
    assert (tmp_path / "pendings.json").exists()  # the old files stay, as a backup
    assert clients.names == [GENERAL, "Assistance Connect"] and clients.current == GENERAL
    general.pendings.write_text("{}")
    make(tmp_path)  # only once: later starts never copy over a client's data again
    assert general.pendings.read_text() == "{}"
