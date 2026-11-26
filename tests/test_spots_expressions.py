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
    overlay = SimpleNamespace(head_y=head_y, card_top=card_top, card_bottom=200 if card_top else None)
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
