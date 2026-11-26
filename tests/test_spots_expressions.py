from types import SimpleNamespace

from kawaii.body.expressions import Expressions
from kawaii.layout.spots import Spots
from kawaii.render.painter import NOTES_H


class ExpModel:
    def __init__(self):
        self.on, self.resets = set(), 0

    def AddExpression(self, e):
        self.on.add(e)

    def RemoveExpression(self, e):
        self.on.discard(e)

    def ResetExpressions(self):
        self.on.clear()
        self.resets += 1


def test_expressions_toggle_like_vtube_studio():
    model = ExpModel()
    exp = Expressions(model)
    exp.toggle("chibi")
    exp.toggle("glasses")
    exp.toggle("chibi")
    assert exp.active == {"glasses"} == model.on
    exp.toggle(None)
    assert exp.active == set() and model.resets == 1


def make(card_top=None, head_y=300, box=(100, 300)):
    layout = SimpleNamespace(left=150, size=(400, 600), body_box=box)
    overlay = SimpleNamespace(head_y=head_y, card_top=card_top, card_bottom=200 if card_top else None,
                              rect_of=lambda kind, name=None: None)
    win = SimpleNamespace(width=550, height=830)
    return Spots(layout, overlay, win)


def test_head_is_the_top_centre_of_her_outline():
    assert make().head() == (150 + 200, 300)
    assert make(box=None, head_y=None).head() == (150 + 200, NOTES_H + 16)


def test_agent_icons_float_up_and_aside():
    spots = make()
    assert spots.agent(1) == (350 + 118, 260)
    assert spots.agent(-1) == (350 - 118, 260)


def test_agent_icons_move_under_an_open_card():
    assert make(card_top=10).agent(1) == (468, 330)


def test_github_badge_floats_above_her_head():
    assert make().github() == (350, 222)
    assert make(card_top=10).github() == (232, 330 + 66)


def test_other_apps_stack_in_pairs_under_the_agents():
    spots = make()
    assert spots.app(0) == (468, 260 + 54)
    assert spots.app(1) == (232, 260 + 54)
    assert spots.app(2) == (468, 260 + 108)


def test_app_icons_never_fall_off_the_bottom():
    assert make().app(40)[1] == 830 - 40


def test_icons_stay_clear_of_the_side_buttons_on_portrait_screens():
    spots = make()
    spots.layout.left = 0  # portrait: the buttons float at the left edge, beside her head
    spots.layout.body_box = (0, 200)
    assert spots.agent(-1)[0] >= 150 + 26
    assert spots.app(1)[0] >= 150 + 26


def test_icons_drop_below_the_top_right_stack_when_it_is_in_the_way():
    spots = make()
    stack = {("clocks", None): (400, 70, 540, 420), ("focus_toggle", None): (400, 38, 540, 62)}
    spots.overlay.rect_of = lambda kind, name=None: stack.get((kind, name))
    x, y = spots.agent(1)
    assert y >= 420 + 30  # under the clocks, not over them
    assert spots.app(0)[1] > y  # the other apps keep stacking under it
    assert spots.agent(-1) == (232, 260)  # the left side is clear of the stack: unchanged
