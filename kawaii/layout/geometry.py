"""Measurements of her area and outline (pure numpy, no GL)."""

import numpy as np

MIN_MODEL, MAX_MODEL = (300, 360), (1600, 2200)  # her area, in px
SILHOUETTE_BAND = 24  # px; input-region rows follow her outline in bands this tall
SILHOUETTE_PAD = 14
FIT_PAD = 0.03  # space left around her when fitting, as a fraction of the area


def clamp_size(w, h):
    return (int(min(MAX_MODEL[0], max(MIN_MODEL[0], w))), int(min(MAX_MODEL[1], max(MIN_MODEL[1], h))))


def is_portrait(output):
    return bool(output and output.h > output.w)


def silhouette_rects(alpha, left, top):
    """Row bands (window coords) around her outline, for the input region."""
    model_h, model_w = alpha.shape
    rects = []
    for y0 in range(0, model_h, SILHOUETTE_BAND):
        cols = np.flatnonzero(alpha[y0:y0 + SILHOUETTE_BAND].any(axis=0))
        if cols.size:
            x0 = max(0, cols[0] - SILHOUETTE_PAD)
            x1 = min(model_w, cols[-1] + 1 + SILHOUETTE_PAD)
            rects.append((left + x0, top + y0, x1 - x0, min(SILHOUETTE_BAND, model_h - y0)))
    return rects


def body_box(alpha):
    """Her left/right extent in her area (px), or None when nothing is drawn."""
    cols = np.flatnonzero(alpha.any(axis=0))
    return (int(cols[0]), int(cols[-1]) + 1) if cols.size else None


def top_row(alpha):
    """The first row with any of her in it (the top of her head)."""
    rows = np.flatnonzero(alpha.any(axis=1))
    return int(rows[0]) if rows.size else None


def stroll_room(size, box):
    """How far (offset units) she may stroll each way: the free width beside her."""
    if not box:
        return 0.0
    mw, mh = size
    return max(0.0, (mw - (box[1] - box[0])) / 2 - 8) / (max(mw, mh) / 2)


def fit_transform(alpha, scale, offset, pad=FIT_PAD):
    """Scale/offset that make her whole body fill the area: centred, feet just above the bottom.

    Cubism scales about the area centre and SetOffset moves by half the area height per
    unit on both axes (y up), so one measurement of her bounding box is enough. Returns
    (scale, offset, clipped); clipped means she touched an edge, so the box was incomplete
    and another pass is needed.
    """
    model_h, model_w = alpha.shape
    ys, xs = np.flatnonzero(alpha.any(axis=1)), np.flatnonzero(alpha.any(axis=0))
    if not xs.size:
        return scale, offset, False
    bx0, bx1, by0, by1 = xs[0], xs[-1] + 1, ys[0], ys[-1] + 1
    clipped = bx0 == 0 or by0 == 0 or bx1 == model_w or by1 == model_h
    k = min(model_w * (1 - 2 * pad) / (bx1 - bx0), model_h * (1 - 2 * pad) / (by1 - by0))
    if clipped:
        k = min(k, 0.8)  # shrink first, then measure the whole of her
    unit = max(model_w, model_h) / 2
    # Her centre at scale 1 without offset, relative to the area centre (px, y down).
    mx = ((bx0 + bx1) / 2 - model_w / 2 - offset[0] * unit) / scale
    my = ((by0 + by1) / 2 - model_h / 2 + offset[1] * unit) / scale
    new_scale = scale * k
    target_y = model_h * (1 - pad) - (by1 - by0) * k / 2 - model_h / 2
    return new_scale, (-new_scale * mx / unit, (new_scale * my - target_y) / unit), clipped
