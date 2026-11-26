import numpy as np
import pytest

from kawaii.layout import geometry


def blob(h=100, w=80, box=(20, 60, 10, 90)):
    """A coverage mask with her bounding box at x0..x1, y0..y1."""
    alpha = np.zeros((h, w), bool)
    x0, x1, y0, y1 = box
    alpha[y0:y1, x0:x1] = True
    return alpha


def test_clamp_size_keeps_her_area_in_bounds():
    assert geometry.clamp_size(10, 10) == geometry.MIN_MODEL
    assert geometry.clamp_size(99999, 99999) == geometry.MAX_MODEL
    assert geometry.clamp_size(500.7, 700.2) == (500, 700)


def test_is_portrait():
    class Out:
        def __init__(self, w, h):
            self.w, self.h = w, h

    assert geometry.is_portrait(Out(1080, 1920))
    assert not geometry.is_portrait(Out(1920, 1080))
    assert not geometry.is_portrait(None)


def test_body_box_and_top_row():
    alpha = blob()
    assert geometry.body_box(alpha) == (20, 60)
    assert geometry.top_row(alpha) == 10
    empty = np.zeros((10, 10), bool)
    assert geometry.body_box(empty) is None
    assert geometry.top_row(empty) is None


def test_silhouette_rects_follow_the_outline_in_bands():
    alpha = blob(h=48, w=80, box=(20, 60, 0, 48))
    rects = geometry.silhouette_rects(alpha, left=150, top=230)
    pad, band = geometry.SILHOUETTE_PAD, geometry.SILHOUETTE_BAND
    assert rects == [(150 + 20 - pad, 230, 40 + 2 * pad, band), (150 + 20 - pad, 230 + band, 40 + 2 * pad, band)]


def test_silhouette_rects_skip_empty_bands_and_clip_padding():
    alpha = np.zeros((48, 30), bool)
    alpha[30:40, 0:30] = True  # only the second band, touching both edges
    assert geometry.silhouette_rects(alpha, left=0, top=0) == [(0, 24, 30, 24)]


def test_fit_transform_without_her_changes_nothing():
    assert geometry.fit_transform(np.zeros((10, 10), bool), 1.5, (0.1, 0.2)) == (1.5, (0.1, 0.2), False)


def test_fit_transform_scales_her_to_fill_the_area():
    scale, offset, clipped = geometry.fit_transform(blob(), 1.0, (0.0, 0.0), pad=0.0)
    assert not clipped
    assert scale == pytest.approx(min(80 / 40, 100 / 80))


def test_fit_transform_shrinks_first_when_she_is_clipped():
    scale, _, clipped = geometry.fit_transform(blob(box=(0, 80, 0, 100)), 1.0, (0.0, 0.0))
    assert clipped
    assert scale <= 0.8


def test_stroll_room_is_the_free_width_beside_her():
    assert geometry.stroll_room((400, 600), None) == 0.0
    assert geometry.stroll_room((400, 600), (100, 300)) == pytest.approx((100 - 8) / 300)
    assert geometry.stroll_room((400, 600), (0, 400)) == 0.0
