"""Stand-ins for the GL model, the painted overlay, the clipboard and other edges of the app."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from kawaii.cards.base import Screen


class FakeModel:
    """Records what the body asks of the Live2D model."""

    def __init__(self):
        self.params = {}  # param -> (value, weight) last set
        self.calls = []  # every SetParamById, in order
        self.added = {}
        self.offset = None
        self.scale = None

    def SetParamById(self, param, value, weight=1.0):
        self.params[param] = (value, weight)
        self.calls.append((param, value, weight))

    def AddParamById(self, param, value):
        self.added[param] = self.added.get(param, 0.0) + value

    def SetOffset(self, x, y):
        self.offset = (x, y)

    def SetScale(self, scale):
        self.scale = scale

    def Resize(self, w, h):
        self.size = (w, h)

    def Drag(self, x, y):
        self.looking_at = (x, y)


class FakeOverlay(SimpleNamespace):
    def __init__(self, rects=None, **kw):
        super().__init__(caret=None, card_top=None, card_bottom=None, head_y=None, hover=None,
                         pk_rows=10, dec_rows=10, obs_rows=10, rules_rows=10, rules_skip=0, pr_rows=10, **kw)
        self.rects = rects or {}
        self.under = None  # what overlay.hit returns

    def rect_of(self, kind, name=None):
        return self.rects.get((kind, name))

    def hit(self, x, y):
        return self.under


def make_screen(rects=None):
    return Screen(FakeOverlay(rects), MagicMock(name="fx"))


class FakeClipboard:
    def __init__(self, text=None, available=True, works=True):
        self.text, self.available, self.works = text, available, works

    def get(self):
        return self.text

    def set(self, text):
        if self.works:
            self.text = text
        return self.works
