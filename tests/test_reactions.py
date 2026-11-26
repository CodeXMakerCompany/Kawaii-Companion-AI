"""She thinks while Kiro/Claude agents work, goes 'huh?' when one waits on you, and gets it when they finish."""

from kawaii.body.body import Body
from kawaii.body.reactions import AgentReactions

RIGHT, LEFT = 1, -1


def make():
    body = Body()
    return body, AgentReactions(body)


def test_thinks_while_an_agent_works_looking_at_its_side():
    body, r = make()
    assert r.update(0.0, working=[LEFT], waiting=[]) == []
    assert body.thinker.active and body.thinker.side == LEFT
    assert r.ponder_at == 0.7


def test_gets_it_when_the_last_agent_is_done():
    body, r = make()
    r.update(0.0, working=[RIGHT], waiting=[])
    assert r.update(1.0, working=[], waiting=[]) == ["aha"]
    assert not body.thinker.active


def test_does_not_interrupt_another_routine():
    body, r = make()
    body.toggle(body.dancer)
    r.update(0.0, working=[RIGHT], waiting=[])
    assert body.dancer.active and not body.thinker.active


def test_waiting_agent_turns_thinking_into_huh():
    body, r = make()
    r.update(0.0, working=[RIGHT], waiting=[])
    r.update(1.0, working=[], waiting=[LEFT])
    assert body.huh.active and body.huh.side == LEFT
    assert not body.thinker.active and body.thinker.aha is None  # not done: it needs you


def test_huh_relaxes_once_answered():
    body, r = make()
    r.update(0.0, working=[], waiting=[RIGHT])
    r.update(1.0, working=[], waiting=[])
    assert not body.huh.active


def test_each_new_double_take_gets_its_burst():
    body, r = make()
    events = r.update(0.0, working=[], waiting=[RIGHT])
    assert events == ["puzzled"]
    assert r.update(0.1, working=[], waiting=[RIGHT]) == []


def test_dismissed_thinking_stays_off_until_agents_finish():
    body, r = make()
    r.update(0.0, working=[RIGHT], waiting=[])
    body.toggle(body.thinker)  # you stop her
    r.user_toggled_think(0.5)
    r.update(1.0, working=[RIGHT], waiting=[])
    assert not body.thinker.active
    r.update(2.0, working=[], waiting=[])
    r.update(3.0, working=[RIGHT], waiting=[])
    assert body.thinker.active


def test_dismissed_huh_stays_off_while_still_waiting():
    body, r = make()
    r.update(0.0, working=[], waiting=[RIGHT])
    body.toggle(body.huh)
    r.user_toggled_huh()
    r.update(1.0, working=[], waiting=[RIGHT])
    assert not body.huh.active


def test_your_own_huh_looks_at_the_empty_side():
    body, r = make()
    body.toggle(body.huh)
    body.huh.side = LEFT
    r.user_toggled_huh()
    assert body.huh.side == RIGHT


def test_ponders_every_few_seconds_but_not_over_a_card():
    body, r = make()
    r.update(0.0, working=[RIGHT], waiting=[])
    assert r.ponder(0.5, card_open=lambda: False) is None
    assert r.ponder(0.8, card_open=lambda: True) is None
    assert r.ponder(0.8, card_open=lambda: False) is False  # trail to the icon, no cloud
    assert r.ponder(1.0, card_open=lambda: False) is None
    body.toggle(body.thinker)
    body.toggle(body.thinker)
    r.working = False
    assert r.ponder(8.0, card_open=lambda: False) is True
