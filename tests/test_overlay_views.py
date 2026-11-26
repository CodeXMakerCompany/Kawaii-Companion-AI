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

CARDS = ("pendings", "calendar", "prs", "decoder", "picker", "settings", "observe", "rules")


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
    assert kinds.count("button") == 4


def test_views_draw_through_the_painter_primitives(cards):
    """A view is a plain function: (painter, ImageDraw, its card's payload)."""
    from PIL import Image, ImageDraw

    ov = overlay()
    ov.begin_frame(Image.new("RGBA", (ov.w, ov.h)))
    VIEWS["settings"].draw(ov, ImageDraw.Draw(ov.image), dict(cards["settings"], open=True))
    assert ov.rect_of("set_done")
