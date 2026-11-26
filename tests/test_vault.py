"""The Vault: secret keys grouped by the reason you keep them, in a plain text file only
you can read. The screen only ever gets them masked, and nothing sends them to an AI."""

import os
import stat

from kawaii.features.vault import TEMP_SECONDS, Vault, mask


class Clock:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


def make(tmp_path, clock=None):
    return Vault(tmp_path / "vault.txt", now=clock or Clock())


def test_reasons_come_first_like_business_rules(tmp_path):
    v = make(tmp_path)
    assert v.add_reason("  Acme   staging ") == 0
    assert v.add_reason("acme staging") == 0  # the same reason, any case
    assert v.add_reason("") is None
    assert v.reasons[0]["name"] == "Acme staging"


def test_keys_need_a_name_and_a_value(tmp_path):
    v = make(tmp_path)
    ri = v.add_reason("OpenAI")
    assert v.add_key(ri, "dev", "sk-abc")
    assert not v.add_key(ri, "", "sk-abc")
    assert not v.add_key(ri, "dev", "  ")
    assert not v.add_key(5, "dev", "x")


def test_saved_as_a_text_file_only_you_can_read(tmp_path):
    v = make(tmp_path)
    ri = v.add_reason("OpenAI")
    v.add_key(ri, "dev key", "sk-abc\t123\n")  # tabs and newlines would break the file
    v.add_reason("Empty one")
    path = tmp_path / "vault.txt"
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    text = path.read_text()
    assert text.startswith("#") and "OpenAI\tdev key\tsk-abc123\t\n" in text
    again = make(tmp_path)
    assert [r["name"] for r in again.reasons] == ["OpenAI", "Empty one"]
    assert again.reasons[0]["keys"][0] == {"name": "dev key", "secret": "sk-abc123", "expires": None}


def test_a_hand_edited_file_is_read_too(tmp_path):
    (tmp_path / "vault.txt").write_text("# mine\nAWS\taccess\tAKIA123\n\nbroken line without tabs\nAWS\tsecret\txyz\t\n")
    v = make(tmp_path)
    assert [k["name"] for k in v.reasons[0]["keys"]] == ["access", "secret"]
    assert [r["name"] for r in v.reasons] == ["AWS", "broken line without tabs"]


def test_temporary_keys_delete_themselves_after_a_day(tmp_path):
    clock = Clock()
    v = make(tmp_path, clock)
    ri = v.add_reason("Acme")
    v.add_key(ri, "temp token", "abc", temporary=True)
    v.add_key(ri, "keeps", "def")
    assert v.reasons[0]["keys"][0]["expires"] == clock.t + TEMP_SECONDS
    clock.t += TEMP_SECONDS - 1
    assert not v.purge()
    clock.t += 2
    assert v.purge()
    assert [k["name"] for k in v.reasons[0]["keys"]] == ["keeps"]
    assert [k["name"] for k in make(tmp_path, clock).reasons[0]["keys"]] == ["keeps"]


def test_expired_keys_are_dropped_when_read(tmp_path):
    (tmp_path / "vault.txt").write_text("Acme\told\tabc\t5\n")
    assert make(tmp_path).reasons[0]["keys"] == []


def test_remove(tmp_path):
    v = make(tmp_path)
    ri = v.add_reason("A")
    v.add_key(ri, "k", "v")
    v.remove_key(ri, 0)
    assert v.reasons[0]["keys"] == []
    v.remove_reason(0)
    assert v.reasons == []


def test_mask_never_shows_the_middle():
    assert mask("sk-proj-1234567890abcdef") == "sk-p…cdef"
    assert mask("short") == "••••••••"
    assert "1234567890" not in mask("sk-proj-1234567890abcdef")
