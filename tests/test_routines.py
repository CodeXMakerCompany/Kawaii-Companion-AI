"""Each routine eases in when started, drives her parameters while on, and eases back out."""

import random

import pytest

from kawaii.body.dance import Dancer
from kawaii.body.greet import Greeter
from kawaii.body.huh import Huh
from kawaii.body.pose import PoseShow
from kawaii.body.talk import TalkSimulator
from kawaii.body.think import Thinker
from kawaii.body.walk import Walker


@pytest.fixture(autouse=True)
def seeded():
    random.seed(1)


def run(routine, seconds, dt=1 / 30, **kw):
    out = None
    for _ in range(int(seconds / dt)):
        out = routine.update(dt, **kw)
    return out


@pytest.mark.parametrize("make", [Dancer, PoseShow, Greeter, Thinker, Huh])
def test_still_until_started(make):
    assert make().update(1 / 30) is None


@pytest.mark.parametrize("make", [Dancer, PoseShow, Greeter, Thinker, Huh])
def test_eases_in_then_back_out(make):
    r = make()
    r.toggle()
    assert r.active
    run(r, 1.0)
    assert r.env == pytest.approx(1.0)
    r.toggle() if r.active else None
    assert not r.active
    assert run(r, 3.0) is None
    assert r.env == 0.0


def test_dancer_bounces_and_cycles_hand_poses():
    d = Dancer()
    d.toggle()
    params, bounce = run(d, 2.5)
    assert bounce >= 0
    assert sum(params[p][0] for p in Dancer.POSES) == pytest.approx(1.0)


def test_pose_show_counts_through_its_poses_then_relaxes():
    p = PoseShow()
    p.toggle()
    assert p.label() == "Wink 1/5"
    run(p, PoseShow.HOLD + 0.1)
    assert p.label() == "Shoulder 2/5"
    run(p, PoseShow.HOLD * 5)
    assert not p.active and p.label() is None


def test_walker_strolls_only_when_there_is_room():
    w = Walker()
    w.toggle()
    _, (dx, _) = run(w, 2.0, room=0.5)
    assert dx != 0
    w2 = Walker()
    w2.toggle()
    _, (dx2, _) = run(w2, 2.0, room=0.0)
    assert dx2 == 0


def test_greeter_is_one_shot():
    g = Greeter()
    g.toggle()
    run(g, Greeter.LENGTH + 0.1)
    assert not g.active


def test_thinker_aha_only_when_finished_on_purpose():
    t = Thinker()
    t.toggle()
    run(t, 1.0)
    t.stop(aha=False)
    assert t.aha is None
    t.toggle()
    t.stop()
    assert t.aha == 0.0


def test_huh_counts_double_takes():
    h = Huh()
    h.toggle()
    assert h.beats == 1
    run(h, Huh.BEAT + 7.5)
    assert h.beats == 2


def test_talk_simulator_moves_the_mouth_then_closes():
    t = TalkSimulator()
    t.start(0.0, 1.0)
    assert t.seconds_left(0.0) == 1
    now, opened = 0.0, 0.0
    while now < 1.0:
        now += 1 / 30
        mouth, _ = t.update(now, 1 / 30) or (0.0, 0.0)
        opened = max(opened, mouth)
    assert opened > 0.3
    assert not t.active and t.seconds_left(now) is None
    while t.update(now, 1 / 30):
        now += 1 / 30
    assert t.mouth < 0.01
