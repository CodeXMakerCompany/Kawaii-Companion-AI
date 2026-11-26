from types import SimpleNamespace

import pytest

from kawaii.layout.layout import Layout
from kawaii.render.painter import NOTES_H, PANEL_W
from kawaii.settings import StateStore
from tests.fakes import FakeModel


class FakeWindow:
    def __init__(self, output=None):
        self.output, self.margin, self.width, self.height = output, [80, 80], 570, 850
        self.geometry = None

    def set_geometry(self, left, top, w, h):
        self.geometry, self.margin, self.width, self.height = (left, top, w, h), [left, top], w, h


def output(name, w, h):
    return SimpleNamespace(name=name, w=w, h=h)


def make(tmp_path, win=None, **kw):
    store = StateStore(tmp_path / "s.json")
    win = win or FakeWindow(output("DP-1", 2560, 1440))
    kw.setdefault("default_size", (420, 620))
    return Layout(FakeModel(), win, store, now=lambda: 100.0, **kw), store, win


def test_wide_monitor_gets_the_default_size_and_a_fit(tmp_path):
    layout, _, win = make(tmp_path)
    layout.apply(win.output)
    assert layout.left == PANEL_W
    assert layout.pending_geometry == (80, 80, PANEL_W + 420, NOTES_H + 620)
    assert layout.fit_due == pytest.approx(100.15)


def test_portrait_monitor_is_filled_without_the_button_column(tmp_path):
    layout, _, _ = make(tmp_path)
    layout.apply(output("HDMI-1", 1080, 1920))
    assert layout.left == 0
    assert layout.pending_geometry == (0, 0, 1080, 1920)


def test_saved_layouts_come_back_per_monitor(tmp_path):
    layout, store, win = make(tmp_path)
    store.remember_layout("DP-1", {"margin": [5, 6], "model_size": [500, 700], "left": PANEL_W,
                                   "scale": 1.4, "offset": [0.1, -0.2]})
    layout.apply(win.output)
    assert layout.pending_geometry == (5, 6, PANEL_W + 500, NOTES_H + 700)
    assert (layout.scale, layout.offset) == (1.4, (0.1, -0.2))
    assert layout.model.scale == 1.4 and layout.fit_due is None


def test_remember_saves_this_monitors_layout(tmp_path):
    layout, store, win = make(tmp_path)
    layout.set_transform(2.0, (0.5, 0.25))
    layout.remember()
    saved = StateStore(tmp_path / "s.json").layout_for("DP-1")
    assert saved["scale"] == 2.0 and saved["offset"] == [0.5, 0.25] and saved["margin"] == [80, 80]


def test_snapshots_never_overwrite_the_saved_layout(tmp_path):
    layout, store, _ = make(tmp_path, snapshot=True)
    layout.remember()
    assert store.layout_for("DP-1") is None


def test_fixed_scale_skips_fitting(tmp_path):
    layout, _, win = make(tmp_path, fixed_scale=1.7)
    layout.request_fit()
    assert layout.scale == 1.7 and layout.fit_due is None and layout.silhouette_due is not None


def test_zoom_is_clamped(tmp_path):
    layout, _, _ = make(tmp_path)
    for _ in range(60):
        layout.zoom(1)
    assert layout.scale == 5.0
    for _ in range(60):
        layout.zoom(-1)
    assert layout.scale == 0.2


def test_resizing_from_the_left_edge_keeps_the_right_edge(tmp_path):
    layout, _, win = make(tmp_path)
    win.margin = [300, 80]
    layout.size = (420, 620)
    layout.begin_drag("left", (10, 300))
    layout.drag_to(-90, 300)  # 100px further left
    assert layout.pending_geometry == (200, 80, PANEL_W + 520, NOTES_H + 620)


def test_resize_is_clamped_to_her_minimum(tmp_path):
    layout, _, win = make(tmp_path)
    layout.size = (420, 620)
    layout.begin_drag("right", (500, 300))
    layout.drag_to(0, 300)
    assert layout.pending_geometry[2] - layout.left == 300


def test_end_drag_says_whether_she_was_resized(tmp_path):
    layout, _, _ = make(tmp_path)
    layout.begin_drag("bottom", (0, 0))
    assert layout.end_drag() is True and layout.drag is None
    assert layout.end_drag() is None


def test_apply_pending_geometry_resizes_the_model(tmp_path):
    layout, _, win = make(tmp_path)
    layout.pending_geometry = (10, 20, PANEL_W + 500, NOTES_H + 700)
    assert layout.apply_pending_geometry()
    assert layout.size == (500, 700) and win.geometry == (10, 20, PANEL_W + 500, NOTES_H + 700)
    assert layout.pending_geometry is None
    assert not layout.apply_pending_geometry()
