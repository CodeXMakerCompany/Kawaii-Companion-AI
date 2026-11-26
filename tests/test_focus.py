"""Focus mode: a countdown during which she keeps quiet, while a dropdown under the system
pill counts everything that is waiting, so you can see it at a glance instead."""

from kawaii.focus import FOCUS_MINUTES, Focus, summary_rows, summary_sentence
from kawaii.settings import StateStore
from tests.test_vault import Clock


def make(tmp_path, clock=None):
    clock = clock or Clock()
    return Focus(StateStore(tmp_path / "s.json"), now=clock), clock


def test_off_until_switched_on(tmp_path):
    focus, _ = make(tmp_path)
    assert not focus.on and not focus.quiet and focus.left() is None and focus.label() is None


def test_counts_down_from_25_minutes(tmp_path):
    focus, clock = make(tmp_path)
    focus.toggle()
    assert focus.on and focus.quiet
    assert focus.left() == FOCUS_MINUTES * 60 == 1500 and focus.label() == "25:00"
    clock.t += 61.2
    assert focus.label() == "23:59"


def test_long_sessions_show_hours(tmp_path):
    focus, _ = make(tmp_path)
    focus.start(minutes=90)
    assert focus.label() == "1:30:00"


def test_ends_by_itself_once(tmp_path):
    focus, clock = make(tmp_path)
    focus.start()
    assert focus.tick() is False
    clock.t += FOCUS_MINUTES * 60
    assert focus.tick() is True
    assert not focus.on and focus.tick() is False


def test_plus_five_and_end(tmp_path):
    focus, _ = make(tmp_path)
    focus.start()
    focus.extend()
    assert focus.left() == 30 * 60
    focus.open = True
    focus.stop()
    assert not focus.on and not focus.open


def test_never_longer_than_three_hours(tmp_path):
    focus, _ = make(tmp_path)
    focus.start(minutes=178)
    focus.extend()
    assert focus.left() == 180 * 60


def test_survives_a_restart(tmp_path):
    focus, clock = make(tmp_path)
    focus.start()
    again, _ = make(tmp_path, clock)
    assert again.on and again.left() == 1500
    focus.stop()
    assert not make(tmp_path, clock)[0].on


def test_a_session_that_ended_while_she_was_off_is_over(tmp_path):
    focus, clock = make(tmp_path)
    focus.start()
    clock.t += 3000
    assert not make(tmp_path, clock)[0].on


COUNTS = {"agents_waiting": 1, "agents_working": 2, "pr_comments": 3, "reminders": 0, "alarms": 0,
          "endpoints_down": 1, "pendings": 4}


def test_summary_rows_list_every_countable_thing_in_order():
    rows = summary_rows(COUNTS)
    assert [r[0] for r in rows] == ["Agents waiting on you", "Agents working", "PR comments", "Reminders due",
                                    "System alarms", "Endpoints down", "Pendings open"]
    assert [r[1] for r in rows] == [1, 2, 3, 0, 0, 1, 4]


def test_summary_sentence_names_what_needs_you():
    assert summary_sentence(COUNTS) == "1 agent waiting on you, 3 PR comments and 1 endpoint down."
    assert summary_sentence({"pr_comments": 1}) == "1 PR comment."
    assert summary_sentence({"agents_working": 2, "pendings": 5}) == "Nothing new came in."
