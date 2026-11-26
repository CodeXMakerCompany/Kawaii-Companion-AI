"""Each card's drawing lives with the card (kawaii/cards/views); the overlay lays out the
side column and the bubbles and draws whichever card is open."""

import datetime
from pathlib import Path

import pytest

from kawaii.cards.views import VIEWS
from kawaii.features.pendings import Pendings
from kawaii.features.reminders import Events
from kawaii.features.rules import Rulebook
from kawaii.render.overlay import Overlay

CARDS = ("clients", "pendings", "calendar", "prs", "decoder", "picker", "settings", "observe", "rules", "vault")


@pytest.fixture
def cards(tmp_path):
    pend = Pendings(tmp_path / "p.json")
    pend.add("Buy milk")
    events = Events(tmp_path / "e.json")
    events.add("2026-11-25", "Stretch")
    rules = Rulebook(tmp_path / "r.json")
    rules.add_company("Acme")
    comment = {"repo": "me/app", "number": 7, "title": "Login", "body": "nice", "kind": "comment",
               "author": "ana", "at": "2020-01-01T00:00:00Z", "url": "u"}
    return {
        "pendings": {"open": False, "pendings": pend, "draft": ""},
        "calendar": {"open": False, "month": (2026, 11), "selected": "2026-11-25", "draft": "", "editing": None,
                     "today": datetime.date(2026, 11, 25), "events": events, "due_count": 1, "yearly": False},
        "prs": {"open": False, "items": [comment], "skip": 0, "checked": None},
        "decoder": {"open": False, "draft": "", "result": None, "status": "", "explanation": None, "skip": 0,
                    "clipboard": True},
        "picker": {"open": False, "step": "folder", "path": Path("/home/me/Projects"), "entries": [("app", True)],
                   "repo": None, "branches": [], "base": "main", "filter": "", "selected": None, "skip": 0,
                   "status": ""},
        "settings": {"open": False, "monitors": [("DP-1", 2560, 1440, "")], "choice": "auto", "largest": "DP-1",
                     "available": True, "here": "DP-1"},
        "observe": {"open": False, "endpoints": [], "draft": "", "busy": False, "title": "", "focus": "title",
                    "status": "", "skip": 0, "checked": None},
        "rules": {"open": False, "companies": rules.companies, "company": None, "draft": "", "status": "", "skip": 0},
    }


def overlay():
    ov = Overlay(420, 620, 1.0, 150)
    ov.head_y = 330
    return ov


def test_every_card_has_a_view():
    assert set(VIEWS) == set(CARDS)


def test_closed_cards_draw_only_the_side_column(cards):
    ov = overlay()
    data = ov.render(cards)
    assert len(data) == ov.w * ov.h * 4
    assert ov.card_top is None
    assert ov.rect_of("button", "pendings") and ov.rect_of("action", "decode")


@pytest.mark.parametrize("name, region", [
    ("pendings", ("item", 0)), ("calendar", ("cal_save", None)), ("prs", ("pr_card", None)),
    ("decoder", ("dec_run", None)), ("picker", ("pk_row", 0)), ("settings", ("set_mon", 0)),
    ("observe", ("obs_add", None)), ("rules", ("rules_row", 0)),
])
def test_the_open_card_draws_its_own_click_areas(cards, name, region):
    cards[name] = dict(cards[name], open=True)
    ov = overlay()
    ov.render(cards)
    assert ov.rect_of(*region), region
    assert ov.card_top is not None


def test_button_badges_count_what_waits(cards):
    ov = overlay()
    ov.render(cards)
    kinds = [k for k, _, _ in ov.regions]
    assert kinds.count("button") == 6


def test_views_draw_through_the_painter_primitives(cards):
    """A view is a plain function: (painter, ImageDraw, its card's payload)."""
    from PIL import Image, ImageDraw

    ov = overlay()
    ov.begin_frame(Image.new("RGBA", (ov.w, ov.h)))
    VIEWS["settings"].draw(ov, ImageDraw.Draw(ov.image), dict(cards["settings"], open=True))
    assert ov.rect_of("set_done")


def test_floating_icons_are_clickable(cards):
    ov = overlay()
    ov.render(cards, badges={"warp": lambda: (400, 300)}, gh_badge=lambda: (300, 100))
    assert ov.rect_of("app_badge", "warp") == (374, 270, 426, 330)
    assert ov.rect_of("gh_badge")


def test_vault_view(cards):
    cards["vault"] = {"open": True, "count": 1, "reasons": [{"name": "OpenAI", "count": 1}], "reason": 0,
                      "keys": [{"name": "dev", "masked": "sk-p…cdef", "expires_in": None}], "name": "",
                      "secret_dots": "", "focus": "name", "temporary": False, "status": "", "skip": 0}
    ov = overlay()
    ov.render(cards)
    assert ov.rect_of("vault_row", 0) and ov.rect_of("vault_add") and ov.rect_of("vault_temp")
    assert ov.rect_of("button", "vault")


FOCUS_ON = {"on": True, "label": "24:59", "open": False, "total": 3,
            "rows": [("PR comments", 3), ("Reminders due", 0)]}


def test_the_focus_switch_sits_under_the_system_pill(cards):
    ov = overlay()
    ov.render(cards, focus={"on": False, "label": None, "open": False, "total": 0, "rows": []})
    switch = ov.rect_of("focus_toggle")
    assert switch and ov.rect_of("focus_open") is None
    ov.render(cards, focus=FOCUS_ON)
    assert ov.rect_of("focus_open") and ov.rect_of("focus_panel") is None


def test_the_focus_dropdown_counts_and_has_its_buttons(cards):
    ov = overlay()
    ov.render(cards, focus=dict(FOCUS_ON, open=True))
    panel = ov.rect_of("focus_panel")
    assert panel and ov.rect_of("focus_plus") and ov.rect_of("focus_end")
    assert panel[1] > ov.rect_of("focus_toggle")[3]


def test_the_monitor_layer_paints_the_focus_switch_too(cards):
    """The switch and its dropdown change every second, so they live in the monitor's small
    layer, not the main one; it must be tall enough to hold the dropdown."""
    ov = overlay()
    focus = dict(FOCUS_ON, open=True)
    ov.render(cards, focus=focus)
    bottom = ov.rect_of("focus_panel")[3]
    _, (x, y, w, h) = ov.render_monitor(None, focus)
    assert y + h / ov.px >= bottom
    assert ov.rect_of("focus_panel")  # painting the small layer leaves the click areas alone


def clock(name, group=None, place="", working=True):
    return {"name": name, "place": place, "group": group, "time": "9:00 am", "diff": "", "day": True,
            "working": None if group else working}


CLOCKS = {"expanded": True, "hidden": 0,
          "rows": [clock("Costa Rica"), clock("Argentina"), clock("Colombia"),
                   clock("UTC", "Cloud · AWS"), clock("us-east-1", "Cloud · AWS", "Virginia")]}


def test_customer_clocks_sit_under_the_focus_switch(cards):
    ov = overlay()
    ov.render(cards, focus=FOCUS_ON, clocks=CLOCKS)
    clocks, switch = ov.rect_of("clocks"), ov.rect_of("focus_toggle")
    assert clocks and clocks[1] > switch[3]
    ov.render(cards, focus=dict(FOCUS_ON, open=True), clocks=CLOCKS)
    assert ov.rect_of("clocks")[1] > ov.rect_of("focus_panel")[3]  # pushed down by the open dropdown


def test_the_monitor_layer_paints_the_clocks(cards):
    ov = overlay()
    ov.render(cards, focus=FOCUS_ON, clocks=CLOCKS)
    bottom = ov.rect_of("clocks")[3]
    _, (x, y, w, h) = ov.render_monitor(None, FOCUS_ON, CLOCKS)
    assert y + h / ov.px >= bottom


def test_the_top_resize_arrow_stays_clear_of_the_top_right_stack(cards):
    for left, model_w in ((150, 420), (0, 412)):
        ov = Overlay(model_w, 620, 1.0, left)
        ov.render(cards, focus=FOCUS_ON, clocks=CLOCKS)
        x0, y0, x1, y1 = ov.rect_of("handle", "top")
        for kind in ("focus_toggle", "focus_open", "clocks"):
            k0, k1 = ov.rect_of(kind)[0], ov.rect_of(kind)[2]
            assert x1 <= k0 or x0 >= k1, (left, kind)


def test_the_clocks_card_has_a_fold_toggle(cards):
    ov = overlay()
    ov.render(cards, focus=FOCUS_ON, clocks=CLOCKS)
    tall = ov.rect_of("clocks")
    assert ov.rect_of("clocks_more")
    folded = {"expanded": False, "hidden": 2, "rows": CLOCKS["rows"][:3]}
    ov.render(cards, focus=FOCUS_ON, clocks=folded)
    assert ov.rect_of("clocks")[3] < tall[3] and ov.rect_of("clocks_more")


def test_the_first_button_says_which_client_you_are_on(cards):
    cards["clients"] = {"open": True, "current": "Acme", "draft": "", "status": "", "skip": 0,
                        "rows": [{"name": "General", "current": False}, {"name": "Acme", "current": True}]}
    ov = overlay()
    ov.render(cards)
    assert ov.rect_of("button", "client") and ov.rect_of("client_row", 1) and ov.rect_of("client_add")
    assert ov.regions.index(("button", "client", ov.rect_of("button", "client"))) < \
        ov.regions.index(("button", "pendings", ov.rect_of("button", "pendings")))


def test_rules_badge_counts_the_clients_rules(cards):
    companies = [{"name": "Acme", "rules": [{"text": "a"}, {"text": "b"}, {"text": "c"}]}, {"name": "Other", "rules": []}]
    cards["rules"] = dict(cards["rules"], companies=companies, company=0, locked=True)
    assert Overlay._badge("rules", cards)[0] == 3
    cards["rules"] = dict(cards["rules"], locked=False, company=None)
    assert Overlay._badge("rules", cards)[0] == 2  # no client: how many companies
