"""Window input reaches the right owner: the open card, her body, the side controls, or a drag."""

from types import SimpleNamespace

from kawaii.body.body import Body
from kawaii.body.expressions import Expressions
from kawaii.body.reactions import AgentReactions
from kawaii.cards.base import Deck
from kawaii.cards.prs import PRCard
from kawaii.cards.settings import SettingsCard
from kawaii.input.keys import BTN_LEFT, BTN_RIGHT, KEY_BACKSPACE, KEY_ESC, KEY_F10, KEY_R
from kawaii.input.router import Router
from kawaii.layout.layout import Layout
from kawaii.layout.spots import Spots
from kawaii.settings import StateStore
from tests.fakes import FakeModel, make_screen
from tests.test_card_prs_settings import FakeMover, FakePRs
from tests.test_spots_expressions import ExpModel


class Keys:
    def __init__(self):
        self.alt_down = self.ctrl_down = False

    def alt(self):
        return self.alt_down

    def ctrl(self):
        return self.ctrl_down


class FakeWin(SimpleNamespace):
    def __init__(self):
        super().__init__(output=SimpleNamespace(name="DP-1", w=2560, h=1440), margin=[80, 80], width=570, height=850,
                         closed=False, xkb=Keys(), cursor=None, placed=None)

    def set_cursor(self, name):
        self.cursor = name

    def local_to_global(self, x, y):
        return x + 1000, y

    def place(self, *args):
        self.placed = args


class Assistant:
    state = "idle"

    def __init__(self):
        self.toggles = 0

    def toggle(self):
        self.toggles += 1


def make(tmp_path):
    store = StateStore(tmp_path / "s.json")
    screen = make_screen({("button", "dance"): (0, 0, 100, 20), ("action", "settings"): (0, 30, 50, 50)})
    overlay = screen.overlay
    overlay.show_handles, overlay.squash, overlay.flash = False, {}, None
    win = FakeWin()
    layout = Layout(FakeModel(), win, store, now=lambda: 0.0)
    body = Body()
    app = SimpleNamespace(
        win=win, overlay=overlay, screen=screen, fx=screen.fx, layout=layout, body=body,
        reactions=AgentReactions(body), spots=Spots(layout, overlay, win), store=store,
        assistant=Assistant(), speaker=SimpleNamespace(react=lambda *a, **k: None),
        expressions=Expressions(ExpModel()), hotkeys={59: "chibi"}, moves_open=True, flashed=None,
        deck=Deck(PRCard(screen, FakePRs()), SettingsCard(screen, store, FakeMover(), here=lambda: None)))
    app.impact_frame = lambda hit: setattr(app, "flashed", hit)
    app.toggle_expression = app.expressions.toggle
    return app, Router(app)


def click(app, router, hit, button=BTN_LEFT):
    app.overlay.under = hit
    router.on_button(button, True)
    router.on_button(button, False)


def test_routine_buttons_drive_her_body(tmp_path):
    app, router = make(tmp_path)
    click(app, router, ("button", "dance"))
    assert app.body.dancer.active
    assert ("button", "dance") in app.screen.presses
    assert app.flashed == ("button", "dance")
    click(app, router, ("action", "walk"))
    assert app.body.walker.active and not app.body.dancer.active


def test_right_clicks_on_buttons_do_nothing(tmp_path):
    app, router = make(tmp_path)
    click(app, router, ("button", "dance"), BTN_RIGHT)
    assert not app.body.busy and not app.screen.presses


def test_card_openers_go_through_the_deck(tmp_path):
    app, router = make(tmp_path)
    click(app, router, ("action", "settings"))
    assert app.deck.current.name == "settings"


def test_dragging_her_moves_the_window(tmp_path):
    app, router = make(tmp_path)
    app.overlay.under = None
    router.on_motion(100, 400)
    router.on_button(BTN_LEFT, True)
    assert app.layout.drag["kind"] == "move" and app.win.cursor == "grabbing"
    router.on_motion(150, 420)
    assert app.win.placed is not None
    router.on_button(BTN_LEFT, False)
    assert app.layout.drag is None


def test_clicking_a_card_background_never_drags(tmp_path):
    app, router = make(tmp_path)
    app.overlay.under = ("pr_card", None)
    router.on_button(BTN_LEFT, True)
    assert app.layout.drag is None


def test_esc_closes_the_open_card_before_quitting(tmp_path):
    app, router = make(tmp_path)
    app.deck.show("settings")
    router.on_key(KEY_ESC, True)
    assert app.deck.current is None and not app.win.closed
    router.on_key(KEY_ESC, True)
    assert app.win.closed


def test_hotkeys_refit_and_expressions(tmp_path):
    app, router = make(tmp_path)
    router.on_key(59, True)
    assert app.expressions.active == {"chibi"}
    router.on_key(KEY_BACKSPACE, True)
    assert app.expressions.active == set()
    router.on_key(KEY_R, True)
    assert app.layout.fit_due == 0.0


def test_alt_f10_toggles_listening_even_with_a_card_open(tmp_path):
    app, router = make(tmp_path)
    app.deck.show("settings")
    app.win.xkb.alt_down = True
    router.on_key(KEY_F10, True)
    assert app.assistant.toggles == 1


def test_wheel_scrolls_an_open_card_else_zooms(tmp_path):
    app, router = make(tmp_path)
    app.overlay.under = None
    router.on_scroll(1)
    assert app.layout.scale > 1.0
    app.deck.show("prs")
    app.overlay.under = ("pr_card", None)
    app.overlay.pr_rows = 5
    router.on_scroll(-2)
    assert app.deck["prs"].skip == 2


def test_hover_shows_a_pointer_over_clickable_things(tmp_path):
    app, router = make(tmp_path)
    app.overlay.under = ("button", "dance")
    router.on_motion(10, 10)
    assert app.win.cursor == "pointer" and app.overlay.hover == ("button", "dance")
    app.overlay.under = ("handle", "left")
    router.on_motion(0, 300)
    assert app.win.cursor == "ew_resize"
