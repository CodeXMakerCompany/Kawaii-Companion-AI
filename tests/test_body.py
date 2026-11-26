import pytest

from kawaii.body.body import RAISE_HAND_PARAM, Body
from tests.fakes import FakeModel


def frame(body, model=None, seconds=0.0, dt=1 / 30, **kw):
    model = model or FakeModel()
    kw.setdefault("hand_up", False)
    kw.setdefault("room", 0.0)
    kw.setdefault("offset", (0.0, 0.0))
    motion = body.update(model, dt, **kw)
    for _ in range(int(seconds / dt)):
        motion = body.update(model, dt, **kw)
    return motion


def test_only_one_routine_at_a_time():
    body = Body()
    body.toggle(body.dancer)
    body.toggle(body.walker)
    assert body.walker.active and not body.dancer.active
    body.toggle(body.walker)
    assert not body.busy


def test_routines_by_button_name():
    body = Body()
    assert body.by_name("think") is body.thinker
    assert body.by_name("huh") is body.huh


def test_free_except_ignores_the_given_routine():
    body = Body()
    body.toggle(body.thinker)
    assert body.free_except(body.thinker)
    assert not body.free_except(body.huh)


def test_raised_hand_eases_in_and_steps_aside_for_routines():
    body, model = Body(), FakeModel()
    frame(body, model, seconds=1.0, hand_up=True)
    assert body.hand == pytest.approx(1.0, abs=0.01)
    assert model.params[RAISE_HAND_PARAM][1] == pytest.approx(1.0, abs=0.01)
    body.toggle(body.dancer)
    frame(body, model, seconds=1.0, hand_up=True)
    model = FakeModel()  # the dance poses the same hand, so look at the first call of one frame
    frame(body, model, hand_up=True)
    assert model.calls[0][0] == RAISE_HAND_PARAM
    assert model.calls[0][2] == pytest.approx(0.0, abs=0.01)


def test_dancing_hops_on_top_of_her_fitted_offset():
    body, model = Body(), FakeModel()
    body.toggle(body.dancer)
    motion = frame(body, model, seconds=0.75, offset=(0.1, 0.2))
    assert motion.shift[0] == 0.0
    assert model.offset == (pytest.approx(0.1), pytest.approx(0.2 + motion.shift[1]))


def test_reports_once_when_she_settles_back_to_rest():
    body, model = Body(), FakeModel()
    body.toggle(body.greeter)
    first = frame(body, model)
    assert first.changed is False  # toggling already redrew; the greeting is still on
    settled = [frame(body, model).settled for _ in range(200)]
    assert settled.count(True) == 1
    assert not body.moving


def test_reports_a_change_when_a_routine_ends_by_itself():
    body, model = Body(), FakeModel()
    body.toggle(body.greeter)
    changes = [frame(body, model).changed for _ in range(200)]
    assert changes.count(True) == 1


def test_talking_drives_the_mouth_and_reports_the_countdown():
    body, model = Body(), FakeModel()
    body.talk(2)
    assert body.talk_left() == 2
    motion = frame(body, model, dt=0.2)
    assert "ParamMouthOpenY" in model.params
    assert not motion.talk_changed
    motion = frame(body, model, dt=1.0)
    assert motion.talk_changed and body.talk_left() == 1
    body.stop_talking()
    assert body.talk_left() is None


def test_voice_lip_sync_overrides_the_mouth():
    body, model = Body(), FakeModel()
    body.update(model, 1 / 30, hand_up=False, room=0.0, offset=(0, 0), voice_mouth=0.7)
    assert model.params["ParamMouthOpenY"] == (0.7, 1.0)
    assert model.added["ParamAngleY"] == pytest.approx(1.4)


def test_toggling_asks_for_a_repaint():
    seen = []
    body = Body(on_toggle=lambda: seen.append(1))
    body.toggle(body.walker)
    assert seen == [1]
