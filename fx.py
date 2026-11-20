"""Sakuga-style hit effects on their own layer: impact stars, smoke puffs, crystal chips,
crescent slashes, speed lines, wedges, glints and the painted sound-effect words
(ドン, ポン, ズザッ, カチッ, ゴゴゴゴ, シュッ).

Ported from Sakuga VFX by Justin Finkelman (MIT License, Copyright (c) 2026,
github.com/finktheartist/sakuga-vfx): the shapes, springs and timings follow its core.js
and components, redrawn with cairo in this project's colours.

Effects live for a fraction of a second. While any is alive the layer is redrawn every
frame, cropped to the pixels it covers and uploaded as one small texture; with nothing
alive it costs nothing. Positions are window coordinates.
"""

import json
import math
import random
import re
from pathlib import Path

import cairocffi as cairo

import ui

WORDS_FILE = Path(__file__).with_name("fx_words.json")
TAU = math.pi * 2


def rgb(r, g, b):
    return r / 255, g / 255, b / 255


# The UI's palette (Sakuga's): white bodies, the lavender shadow tone, a violet outline,
# pink for the needles and wedges, ink for the lettering.
FILL = rgb(*ui.CARD)
SHADE = rgb(*ui.SOFT)
LINE = rgb(*ui.ACCENT)
PINK = rgb(*ui.PINK)
INK = rgb(*ui.INK)


def clamp(v, a=0.0, b=1.0):
    return min(b, max(a, v))


def lerp(a, b, t):
    return a + (b - a) * t


def rnd(a=1.0, b=None):
    return random.random() * a if b is None else a + random.random() * (b - a)


def out(t):  # cubic ease-out
    return 1 - (1 - t) ** 3


def inn(t):  # cubic ease-in
    return t * t * t


def back(t):  # ease-out with a little overshoot
    return 1 + 2.70158 * (t - 1) ** 3 + 1.70158 * (t - 1) ** 2


class Spring:
    """Overshoots and settles instead of stopping dead (semi-implicit Euler, 8 ms steps)."""

    def __init__(self, x=0.0, k=300.0, d=20.0):
        self.x, self.v, self.to, self.k, self.d = x, 0.0, x, k, d

    def step(self, dt):
        if not dt > 0:
            return self.x
        n = math.ceil(dt / 0.008)
        h = dt / n
        for _ in range(n):
            self.v += (-self.k * (self.x - self.to) - self.d * self.v) * h
            self.x += self.v * h
        return self.x

    def settled(self):
        return abs(self.x - self.to) < 0.001 and abs(self.v) < 0.01


class Press:
    """A button press: squashed flat, then springing tall with a little overshoot."""

    def __init__(self, low=0.62, pop=1.16):
        self.s, self.pop = Spring(low, 520, 15), Spring(pop, 300, 12)
        self.s.to = self.pop.to = 1.0

    def step(self, dt):
        """(x scale, y scale), or None once it has settled."""
        y, p = self.s.step(dt), self.pop.step(dt)
        if self.s.settled() and self.pop.settled():
            return None
        return (1 + (1 - y) * 0.55) * p, y * p


def _quad(ctx, qx, qy, x, y):
    """Quadratic curve from the current point, as the cubic cairo draws."""
    x0, y0 = ctx.get_current_point()
    ctx.curve_to(x0 + (qx - x0) * 2 / 3, y0 + (qy - y0) * 2 / 3, x + (qx - x) * 2 / 3, y + (qy - y) * 2 / 3, x, y)


def _poly(ctx, pts, close=True):
    for i, (x, y) in enumerate(pts):
        (ctx.line_to if i else ctx.move_to)(x, y)
    if close:
        ctx.close_path()


def _circles(ctx, cs):
    for x, y, r in cs:
        if r > 0.3:
            ctx.move_to(x + r, y)
            ctx.arc(x, y, r, 0, TAU)


def blob(ctx, cs, lw=1.5, lx=-1.0, arcs=False, deep=1.0):
    """Circles drawn as one shape: outline, shadow tone, then the light side slid up."""
    ctx.save()
    _circles(ctx, cs)
    ctx.set_line_width(lw * 2)
    ctx.set_source_rgb(*LINE)
    ctx.stroke()
    ctx.restore()
    ctx.save()
    _circles(ctx, cs)
    ctx.clip()
    ctx.set_source_rgb(*SHADE)
    ctx.paint()
    r = cs[0][2] if cs else 8
    ctx.save()
    ctx.translate(lx * r * 0.2 * deep, -r * 0.26 * deep)
    _circles(ctx, cs)
    ctx.set_source_rgb(*FILL)
    ctx.fill()
    ctx.restore()
    if arcs:  # the cumulus lines inside the cloud
        ctx.set_source_rgb(*LINE)
        ctx.set_line_width(lw * 0.75)
        for x, y, rr in cs:
            if rr > 3:
                ctx.new_sub_path()
                ctx.arc(x, y, rr, -2.7, -0.5)
        ctx.stroke()
    ctx.restore()


def shape(ctx, build, lw=1.5, off=3.0, fill=FILL):
    """build(ctx) adds a path: outlined, filled in the shadow tone, lit from the top left."""
    ctx.save()
    build(ctx)
    ctx.set_line_width(lw * 2)
    ctx.set_source_rgb(*LINE)
    ctx.stroke()
    ctx.restore()
    ctx.save()
    build(ctx)
    ctx.clip()
    ctx.set_source_rgb(*SHADE)
    ctx.paint()
    ctx.translate(-off * 0.7, -off)
    build(ctx)
    ctx.set_source_rgb(*fill)
    ctx.fill()
    ctx.restore()


def parse_path(d):
    """An SVG path that uses only absolute M, L, C and Z, as [(op, numbers)]."""
    ops, cmd, nums = [], None, []
    for tok in re.findall(r"[MLCZ]|-?(?:\d+\.?\d*|\.\d+)", d):
        if tok in "MLCZ":
            cmd = tok
            if cmd == "Z":
                ops.append(("Z", ()))
            continue
        nums.append(float(tok))
        need = 6 if cmd == "C" else 2
        if len(nums) == need:
            ops.append((cmd, tuple(nums)))
            nums = []
            if cmd == "M":
                cmd = "L"  # further pairs after a move are lines
    return ops


class Effects:
    def __init__(self, enabled=True):
        self.enabled = enabled  # off: every effect call does nothing (reduced motion)
        self.live = []  # [elapsed, life, draw(ctx, k, t)]
        self.timers = []  # [due, fn]
        self.now = 0.0
        self.bounds = (0, 0)  # window size; nothing is drawn outside it
        self._words = {}
        self._dots = None

    @property
    def busy(self):
        return bool(self.live or self.timers)

    def add(self, life, draw):
        if self.enabled:
            self.live.append([0.0, life, draw])

    def later(self, seconds, fn):
        if self.enabled:
            self.timers.append([self.now + seconds, fn])

    def update(self, dt):
        dt = clamp(dt, 0.0, 0.034)  # a stall must not skip the effect
        self.now += dt
        due = sorted((q for q in self.timers if q[0] <= self.now), key=lambda q: q[0])
        if due:
            self.timers = [q for q in self.timers if q[0] > self.now]
        for _, fn in due:
            fn()
        for e in self.live:
            e[0] += dt
        self.live = [e for e in self.live if e[0] < e[1]]

    def render(self):
        """(premultiplied BGRA bytes, (x, y, w, h)) of this frame's effects, or None."""
        w, h = self.bounds
        if not self.live or w <= 0 or h <= 0:
            return None
        rec = cairo.RecordingSurface(cairo.CONTENT_COLOR_ALPHA, (0, 0, w, h))
        ctx = cairo.Context(rec)
        ctx.set_line_join(cairo.LINE_JOIN_ROUND)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        for t, life, draw in self.live:
            ctx.save()
            draw(ctx, t / life, t)
            ctx.restore()
        ix, iy, iw, ih = rec.ink_extents()
        x0, y0 = max(0, math.floor(ix) - 1), max(0, math.floor(iy) - 1)
        x1, y1 = min(w, math.ceil(ix + iw) + 1), min(h, math.ceil(iy + ih) + 1)
        if iw <= 0 or ih <= 0 or x1 <= x0 or y1 <= y0:
            return None
        # Sizes in steps of 32 px, so the texture is not reallocated every frame.
        x1, y1 = min(w, x0 + -(-(x1 - x0) // 32) * 32), min(h, y0 + -(-(y1 - y0) // 32) * 32)
        img = cairo.ImageSurface(cairo.FORMAT_ARGB32, x1 - x0, y1 - y0)
        c = cairo.Context(img)
        c.set_source_surface(rec, -x0, -y0)
        c.paint()
        img.flush()
        return bytes(img.get_data()), (x0, y0, x1 - x0, y1 - y0)

    # ───────── the effects (core.js) ─────────

    def puff(self, x, y, n=5, size=13, vx=0, vy=-18, life=0.8, spread=1):
        """A puff of smoke: lobes swell out with a little overshoot, roll, and shrink away."""
        lobes = [(0, 0, size, 0, 1)] + [((i / n) * TAU + rnd(0.6), rnd(0.25, 0.9) * size * spread,
                                         rnd(0.55, 1) * size, rnd(TAU), rnd(0.6, 1.3)) for i in range(n)]

        def draw(ctx, k, t):
            grow, die, o = back(clamp(t / 0.22)), 1 - inn(clamp((k - 0.55) / 0.45)), out(k)
            px, py, m = x + vx * o * life, y + vy * o * life, 0.5 + o * 0.9
            blob(ctx, [(px + math.cos(a + t * 0.9 * sp) * d * m, py + math.sin(a + t * 0.9 * sp) * d * m - o * 5 * sp,
                        r * grow * die * (1 + math.sin(t * 9 + ph) * 0.05)) for a, d, r, ph, sp in lobes],
                 1.5, lx=0.5, arcs=size > 6.5, deep=1.5)
        self.add(life, draw)

    def burst(self, x, y, r=44, spikes=13, life=0.34):
        """The impact: pink needles, a star in the shadow tone and a white star on top; it
        leaves by its points thinning to nothing."""
        j = [rnd(0.34, 0.5) if i % 2 else rnd(0.75, 1.15) for i in range(spikes * 2)]
        rot = rnd(TAU)
        pins = [(i / 8 * TAU + rnd(0.5), rnd(1.25, 1.75), rnd(0.03, 0.055)) for i in range(8)]

        def star(ctx, rr, turn, inner):
            _poly(ctx, [(x + math.cos(rot + turn + i / len(j) * TAU) * rr * (m * inner if i % 2 else m),
                         y + math.sin(rot + turn + i / len(j) * TAU) * rr * (m * inner if i % 2 else m))
                        for i, m in enumerate(j)])

        def draw(ctx, k, t):
            big = r * out(clamp(k / 0.3))
            hollow = 1 + inn(clamp((k - 0.35) / 0.65)) * 1.3
            r0 = big * 0.6 * min(1.9, hollow)
            for a, ln, w in pins:
                ln *= big
                if ln > r0:
                    _poly(ctx, [(x + math.cos(a - w) * r0, y + math.sin(a - w) * r0),
                                (x + math.cos(a) * ln, y + math.sin(a) * ln),
                                (x + math.cos(a + w) * r0, y + math.sin(a + w) * r0)])
            ctx.set_source_rgb(*PINK)
            ctx.fill()
            star(ctx, big * 1.16, 0.19, hollow)
            ctx.set_source_rgb(*SHADE)
            ctx.fill_preserve()
            ctx.set_source_rgb(*LINE)
            ctx.set_line_width(1.2)
            ctx.stroke()
            shape(ctx, lambda c: star(c, big * 0.84, 0, hollow), 1.4, 3)
        self.add(life, draw)

    def shards(self, x, y, n=7, speed=190, size=5, life=0.75, dir=-math.pi / 2, arc=math.pi, grav=420):
        """Chips of crystal: long facets with one edge line, tumbling and falling."""
        for _ in range(n):
            a, v, s, spin = dir + rnd(-arc, arc) / 2, speed * rnd(0.5, 1.15), size * rnd(0.6, 1.4), rnd(-7, 7)
            pts = [(px * rnd(0.8, 1.2), py * rnd(0.8, 1.2))
                   for px, py in ((-1.4, 0.1), (-0.6, -0.7), (1.2, -0.45), (1.5, 0.15), (0.4, 0.75))]

            def draw(ctx, k, t, a=a, v=v, s=s, spin=spin, pts=pts):
                sc = s * (1 - inn(clamp((k - 0.6) / 0.4)))
                ctx.translate(x + math.cos(a) * v * t, y + math.sin(a) * v * t + grav * t * t)
                ctx.rotate(spin * t + a)
                shape(ctx, lambda c: _poly(c, [(u * sc, w * sc) for u, w in pts]), 1.1, sc * 0.45)
                if sc > 2.5:
                    ctx.set_source_rgb(*LINE)
                    ctx.set_line_width(0.9)
                    ctx.move_to(pts[1][0] * sc, pts[1][1] * sc)
                    ctx.line_to(pts[4][0] * sc, pts[4][1] * sc)
                    ctx.stroke()
            self.add(life * rnd(0.7, 1), draw)

    def ring(self, x, y, rx=40, ry=12, life=0.5, w=5):
        """An outlined hoop that opens out and thins away."""
        def draw(ctx, k, t):
            s, lw = out(k), w * (1 - k)

            def hoop():
                ctx.save()
                ctx.translate(x, y)
                ctx.scale(rx * (0.3 + s), ry * (0.3 + s))
                ctx.arc(0, 0, 1, 0, TAU)
                ctx.restore()
            hoop()
            ctx.set_source_rgb(*LINE)
            ctx.set_line_width(lw + 2.4)
            ctx.stroke()
            if lw > 0.3:
                hoop()
                ctx.set_source_rgb(*FILL)
                ctx.set_line_width(lw)
                ctx.stroke()
        self.add(life, draw)

    def slash(self, x, y, len=110, ang=-0.5, life=0.42, thick=15, col=PINK):
        """A crescent whose head races ahead and whose tail catches up."""
        big = len * 0.9
        cx, cy = x - math.cos(ang - math.pi / 2) * big * 0.86, y - math.sin(ang - math.pi / 2) * big * 0.86
        a0, sweep = ang - math.pi / 2 - 0.62, 1.24

        def draw(ctx, k, t):
            head, tail = out(clamp(k / 0.42)), inn(clamp((k - 0.22) / 0.78))
            if head - tail < 0.01:
                return

            def cres(th):
                n = 26
                pts = [(cx + math.cos(a0 + sweep * lerp(tail, head, i / n)) * big,
                        cy + math.sin(a0 + sweep * lerp(tail, head, i / n)) * big) for i in range(n + 1)]
                for i in range(n, -1, -1):
                    q = i / n
                    a, rr = a0 + sweep * lerp(tail, head, q), big - th * max(0.0, math.sin(q * math.pi)) ** 0.7
                    pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
                _poly(ctx, pts)
            cres(thick)
            ctx.set_source_rgb(*col)
            ctx.fill()
            cres(thick * 0.42)
            ctx.set_source_rgb(*FILL)
            ctx.fill()
            cres(thick)
            ctx.set_source_rgb(*LINE)
            ctx.set_line_width(1.3)
            ctx.stroke()
        self.add(life, draw)

    def lines(self, x, y, n=7, dir=math.pi, len=46, spread=26, life=0.3):
        """Speed lines: strokes that shoot out one way and thin away."""
        for _ in range(n):
            o, ln, d, w = rnd(-spread, spread), len * rnd(0.5, 1.3), rnd(0, 0.25), rnd(1, 2.6)

            def draw(ctx, k, t, o=o, ln=ln, d=d, w=w):
                kk = clamp((k - d) / (1 - d))
                a, b = out(kk), inn(kk)
                if kk <= 0 or w * (1 - b) <= 0:
                    return
                px, py = x - math.sin(dir) * o, y + math.cos(dir) * o
                ctx.move_to(px + math.cos(dir) * ln * b * 1.4, py + math.sin(dir) * ln * b * 1.4)
                ctx.line_to(px + math.cos(dir) * ln * (0.2 + a * 1.2), py + math.sin(dir) * ln * (0.2 + a * 1.2))
                ctx.set_source_rgb(*LINE)
                ctx.set_line_width(w * (1 - b))
                ctx.stroke()
            self.add(life, draw)

    def ticks(self, x, y, n=3, r=16, len=9, dir=-0.9, life=0.4, fan=0.42):
        """Accent wedges that point at something and fly off it."""
        def draw(ctx, k, t):
            a, b = out(clamp(k / 0.5)), inn(clamp((k - 0.4) / 0.6))
            for i in range(n):
                an = dir + (i - (n - 1) / 2) * fan
                r0, r1 = r + len * b * 1.25, r + len * a * 1.25
                hw = 0.07 + 2.2 / (r1 + 8)
                if r1 - r0 >= 0.6:
                    _poly(ctx, [(x + math.cos(an) * r0, y + math.sin(an) * r0),
                                (x + math.cos(an - hw) * r1, y + math.sin(an - hw) * r1),
                                (x + math.cos(an + hw) * r1, y + math.sin(an + hw) * r1)])
            ctx.set_source_rgb(*PINK)
            ctx.fill()
        self.add(life, draw)

    def donut(self, x, y, r=20, vx=30, vy=-50, life=1.0, tilt=-0.25):
        """A smoke ring: a lumpy hoop that drifts off and shrinks."""
        ph = rnd(TAU)

        def draw(ctx, k, t):
            s = back(clamp(t / 0.22)) * (1 - inn(clamp((k - 0.6) / 0.4)))
            if s < 0.03:
                return
            px, py, hole = x + vx * out(k) * life, y + vy * out(k) * life, 0.42 + 0.22 * k
            ct, st = math.cos(tilt), math.sin(tilt)

            def build(c):
                for m, bump in ((1, 0.09), (hole, 0.05)):
                    pts = []
                    for i in range(49):
                        a = i / 48 * TAU
                        rr = r * s * m * (1 + bump * math.sin(a * 9 + ph + t * 2))
                        ex, ey = math.cos(a) * rr, math.sin(a) * rr * 0.52
                        pts.append((px + ex * ct - ey * st, py + ex * st + ey * ct))
                    _poly(c, pts, close=False)
            ctx.save()
            build(ctx)
            ctx.set_line_width(3)
            ctx.set_source_rgb(*LINE)
            ctx.stroke()
            ctx.restore()
            ctx.save()
            ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
            build(ctx)
            ctx.clip()
            ctx.set_source_rgb(*SHADE)
            ctx.paint()
            ctx.translate(r * 0.06, -r * 0.2)
            build(ctx)
            ctx.set_source_rgb(*FILL)
            ctx.fill()
            ctx.restore()
        self.add(life, draw)

    def wob(self, x, y, dir=1, r=16, life=0.45):
        """Wobble marks: the two little arcs beside something that has just stopped."""
        def draw(ctx, k, t):
            if 2.2 * (1 - k) < 0.2:
                return
            c = 0 if dir > 0 else math.pi
            for d in (0, 7):
                ctx.new_sub_path()
                ctx.arc(x - dir * r, y, r + d + out(k) * 8, c - 0.45, c + 0.45)
            ctx.set_source_rgb(*LINE)
            ctx.set_line_width(2.2 * (1 - k))
            ctx.stroke()
        self.add(life, draw)

    def kira(self, x, y, r=9, life=0.6, col=FILL):
        """A glint: a four-pointed sparkle that opens and closes."""
        def draw(ctx, k, t):
            s = r * max(0.0, math.sin(k * math.pi)) ** 0.6
            q = s * 0.16
            ctx.translate(x, y)
            ctx.rotate(math.sin(t * 3) * 0.2)
            ctx.move_to(0, -s)
            _quad(ctx, q, -q, s * 0.7, 0)
            _quad(ctx, q, q, 0, s)
            _quad(ctx, -q, q, -s * 0.7, 0)
            _quad(ctx, -q, -q, 0, -s)
            ctx.set_source_rgb(*col)
            ctx.fill_preserve()
            ctx.set_source_rgb(*PINK)
            ctx.set_line_width(2)
            ctx.stroke()
        self.add(life, draw)

    # ───────── the lettering ─────────

    def _word(self, name):
        if not self._words:
            data = json.loads(WORDS_FILE.read_text(encoding="utf-8"))
            self._words = {k: v for k, v in data.items() if not k.startswith("_")}
        w = self._words[name]
        if isinstance(w, list):  # parsed on first use
            w = self._words[name] = (w[0], w[1], parse_path(w[2]))
        return w

    def _dot_pattern(self):
        """Screentone: ink dots on white, repeated."""
        if self._dots is None:
            tile = cairo.ImageSurface(cairo.FORMAT_ARGB32, 22, 44)
            c = cairo.Context(tile)
            c.set_source_rgb(*FILL)
            c.paint()
            for px, py in ((0, 0), (22, 0), (0, 44), (22, 44), (11, 22)):
                c.move_to(px + 5.2, py)
                c.arc(px, py, 5.2, 0, TAU)
            c.set_source_rgb(*INK)
            c.fill()
            self._dots = tile
        pattern = cairo.SurfacePattern(self._dots)
        pattern.set_extend(cairo.EXTEND_REPEAT)
        return pattern

    def sfx(self, name, x, y, size=64, rot=-0.14, life=0.95, style="solid"):
        """A word lands a size too big and wobbles while it stays. style: solid (ink with a
        white edge), hollow (white with an ink edge) or dotted (screentone letters)."""
        w, h, ops = self._word(name)
        win_w, win_h = self.bounds
        hw, hh = size * 0.55, size * h / w * 0.6  # kept inside the window
        x = clamp(x, hw, win_w - hw) if win_w > 2 * hw else win_w / 2
        y = clamp(y, hh, win_h - hh) if win_h > 2 * hh else win_h / 2
        fill, edge = {"solid": (INK, FILL), "hollow": (FILL, INK), "dotted": (None, INK)}[style]
        spring, last = Spring(0.2, 520, 17), [0.0]
        spring.to = 1.0

        def draw(ctx, k, t):
            sc = spring.step(t - last[0]) * (1 - inn(clamp((k - 0.86) / 0.14))) * size / w
            last[0] = t
            if sc <= 0:
                return
            ctx.translate(x + math.sin(t * 31) * 0.8, y + math.cos(t * 27) * 0.8)
            ctx.rotate(rot + math.sin(t * 6) * 0.03)
            ctx.scale(sc, sc)
            ctx.translate(-w / 2, -h / 2)
            for op, p in ops:
                if op == "M":
                    ctx.move_to(*p)
                elif op == "L":
                    ctx.line_to(*p)
                elif op == "C":
                    ctx.curve_to(*p)
                else:
                    ctx.close_path()
            ctx.set_source_rgb(*edge)
            ctx.set_line_width(w * 0.07)
            ctx.stroke_preserve()
            ctx.fill_preserve()
            if fill:
                ctx.set_source_rgb(*fill)
            else:
                ctx.set_source(self._dot_pattern())
            ctx.fill()
        self.add(life, draw)

    # ───────── moments: what each control does, after the Sakuga components ─────────

    def impact(self, rect, word="don"):
        """The button: an impact star with crystals and four clouds behind it, the word lands
        above it, then wobble marks and smoke rings drift off (sakuga-button)."""
        x0, y0, x1, y1 = rect
        cx, cy, w = (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0
        self.burst(cx, cy, r=56, spikes=17, life=0.48)
        self.shards(cx, cy, n=9, speed=220, size=7, life=0.9, arc=TAU, grav=300)
        for dx, dy in ((-1, -0.5), (1, -1), (-1, 0.9), (1, 1)):
            self.puff(cx + dx * (w / 2 + 4), cy + dy * 18, size=rnd(9, 12), n=5, vx=dx * 36, vy=dy * 24 - 6,
                      life=rnd(0.75, 1.05))
        if word:
            self.sfx(word, cx + 30, cy - 62, size=130, rot=-0.12, life=1.05)
        self.ticks(cx - 66, cy - 48, dir=-2.4, n=2, r=4, len=18, life=0.45)
        self.ticks(cx + 76, cy - 42, dir=-0.7, n=2, r=4, len=18, life=0.45)

        def settle():
            self.wob(x0 - 6, cy, dir=-1)
            self.wob(x1 + 6, cy, dir=1)
            self.donut(cx + 6, cy - 32, r=22, vx=22, vy=-48, life=1.2)
            self.later(0.09, lambda: self.donut(cx + 40, cy - 36, r=13, vx=30, vy=-36, life=1.05))
            self.later(0.17, lambda: self.donut(cx + 64, cy - 32, r=8, vx=36, vy=-28, life=0.9))
            for dx in (-24, 26):
                self.shards(cx + dx, cy + 20, n=2, speed=20, size=5, dir=math.pi / 2, arc=1, grav=380)
        self.later(0.2, settle)

    def done(self, rect):
        """A job finished: a glint and two wedges on the top-right corner."""
        x0, y0, x1, y1 = rect
        self.kira(x1 - 12, y0 + 2, r=12, life=1.0)
        self.ticks(x1 - 2, y0 - 10, dir=-0.8, n=2, r=6, len=12)

    def tap(self, rect):
        """A small button's hit: a little impact star, a few chips and a glint."""
        x0, y0, x1, y1 = rect
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        self.burst(cx, cy, r=30, spikes=13, life=0.36)
        self.shards(cx, cy, n=5, speed=150, size=5, life=0.7, arc=TAU, grav=300)
        self.later(0.15, lambda: self.done(rect))

    def pop(self, rect, word="pon"):
        """Picked: a fan of wedges, two puffs drifting off and a hollow word (sakuga-radio)."""
        x0, y0, x1, y1 = rect
        cx, cy = x1 - 18, (y0 + y1) / 2
        self.ticks(cx, cy, dir=-2.3, n=4, r=16, len=13, fan=0.36, life=0.5)
        self.lines(x0 - 2, cy + 12, n=3, dir=2.6, len=22, spread=5)
        self.puff(cx + 18, cy - 16, size=7, n=3, vx=16, vy=-14, life=0.7)
        self.later(0.12, lambda: self.puff(cx + 40, cy + 4, size=6, n=3, vx=10, vy=-10, life=0.6))
        if word:
            self.sfx(word, cx + 30, cy - 56, size=74, rot=0.06, life=0.8, style="hollow")

    def pick(self, rect):
        """A small pick, for mini buttons: three wedges off the corner and a puff."""
        x0, y0, x1, y1 = rect
        self.ticks(x1 - 3, y0 + 3, dir=-0.95, n=3, r=4, len=11, fan=0.42, life=0.4)
        self.puff(x1 + 2, (y0 + y1) / 2, size=5, n=3, vx=12, vy=-10, life=0.5)

    def poof(self, x, y, size=7):
        """Switched off, cancelled or closed: one small puff."""
        self.puff(x, y, size=size, n=3, life=0.4)

    def check(self, x, y):
        """Ticked: two crescents swing round the box, crystals, a glint, dotted ズザッ
        (sakuga-checkbox)."""
        self.slash(x + 6, y + 2, len=96, ang=-0.42, thick=10, life=0.5)
        self.slash(x - 4, y + 8, len=70, ang=2.72, thick=5, life=0.55)
        self.lines(x - 24, y + 18, n=6, dir=2.75, len=42, spread=10)
        self.shards(x, y, n=6, speed=160, size=5, arc=TAU, grav=260)
        self.later(0.38, lambda: self.kira(x + 18, y - 16, r=8))
        self.sfx("zuza", x + 34, y - 46, size=84, rot=-0.12, style="dotted")

    def scrap(self, rect):
        """Deleted: a cloud and a smoke ring where it was."""
        x0, y0, x1, y1 = rect
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        self.puff(cx, cy, size=9, n=4, life=0.55)
        self.donut(cx + 10, cy - 6, r=12, vx=20, vy=-30, life=0.9)

    def land(self, rect, word="zuza"):
        """Arrived from the left: speed lines, dust under it, dotted word, a wobble
        (sakuga-toast landing)."""
        x0, y0, x1, y1 = rect
        cx, cy, w, h = (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0
        self.lines(x0 - 4, cy, n=9, dir=math.pi, len=56, spread=h / 3)
        for u in (-0.5, -0.36, -0.2):
            self.puff(cx + w * u, y1 + 3, size=rnd(7, 10), n=4, vx=-rnd(10, 30), vy=-8, life=rnd(0.7, 1))
        self.puff(x1 + 6, cy + 8, size=6, n=3, vx=20, life=0.6)
        self.shards(x0, cy + 10, n=4, size=4, dir=math.pi + 0.5, arc=1.6)
        self.ticks(cx + 30, y1 + 10, dir=0.5, n=2, r=4, len=14)
        self.wob(x1 + 5, cy, dir=1)
        if word:
            self.sfx(word, cx - 30, y0 - 30, size=96, rot=-0.1, style="dotted")

    def bubble(self, rect, anchor, word="kachi"):
        """A panel springs out of its button: puffs either side, wedges, a ring off the button
        and a hollow word (sakuga-tooltip). rect: the panel; anchor: the button."""
        x0, y0, x1, y1 = rect
        cx, cy, w = (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0
        ax, ay = (anchor[0] + anchor[2]) / 2, anchor[3]

        def go():
            self.puff(x0 - 6, cy - 10, size=7, n=4, vx=-14, vy=-10, life=0.8)
            self.puff(x1 + 6, cy + 10, size=7, n=4, vx=14, vy=-6, life=0.8)
            self.ticks(x1 - 4, y0 - 4, dir=-1.0, n=3, r=5, len=14, fan=0.36, life=0.5)
            self.ring(ax, ay + 3, rx=w * 0.22, ry=5, life=0.5, w=3)
            if word:
                self.sfx(word, cx, y1 + 30, size=84, rot=-0.08, life=0.8, style="hollow")
        self.later(0.12, go)

    def dust(self, x, y):
        """A key typed: a little dust at the caret, now and then a chip (sakuga-input)."""
        self.puff(x, y + 8, size=rnd(3.5, 5), n=2, vx=rnd(-10, 10), vy=-22, life=0.4)
        if random.random() < 0.35:
            self.shards(x, y + 4, n=2, speed=100, size=3, life=0.5)

    def flash(self, x, y):
        """A photo pose: a big glint, two small ones and a ring, like a camera flash."""
        self.kira(x, y, r=18, life=0.7)
        self.ring(x, y, rx=34, ry=34, life=0.45, w=4)
        self.later(0.1, lambda: self.kira(x - 30, y + 18, r=8, life=0.5))
        self.later(0.18, lambda: self.kira(x + 28, y - 20, r=10, life=0.5))

    def chatter(self, x, y):
        """She starts talking: wedges off both sides of her head, then wobble marks.
        x, y: top centre of her head."""
        self.ticks(x - 44, y + 26, dir=-2.4, n=3, r=6, len=14, life=0.45)
        self.ticks(x + 44, y + 26, dir=-0.7, n=3, r=6, len=14, life=0.45)
        self.later(0.15, lambda: (self.wob(x - 56, y + 56, dir=-1, r=12), self.wob(x + 56, y + 56, dir=1, r=12)))

    def hello(self, x, y):
        """She greets: a glint by her head and a hollow ポン."""
        self.kira(x + 46, y + 14, r=12, life=0.8)
        self.later(0.12, lambda: self.kira(x - 40, y + 30, r=7, life=0.6))
        self.sfx("pon", x + 70, y - 12, size=80, rot=0.06, life=0.9, style="hollow")

    def stride(self, x, y):
        """She sets off walking: dotted ズザッ and speed lines at her feet."""
        self.lines(x - 30, y - 10, n=5, dir=math.pi, len=40, spread=12)
        self.puff(x - 20, y, size=7, n=4, vx=-24, vy=-8, life=0.7)
        self.puff(x + 20, y, size=6, n=3, vx=24, vy=-8, life=0.6)
        self.sfx("zuza", x + 50, y - 50, size=90, rot=-0.1, style="dotted")

    def nudge(self, rect):
        """Get attention: wedges off a corner and wobble marks at both sides."""
        x0, y0, x1, y1 = rect
        cy = (y0 + y1) / 2
        self.ticks(x0 + 4, y0 + 2, dir=-2.3, n=3, r=4, len=12, life=0.45)
        self.wob(x0 - 6, cy, dir=-1, r=10)
        self.wob(x1 + 6, cy, dir=1, r=10)

    def pulse(self, x, y, r):
        """Listening: a round ring opening out from it."""
        self.ring(x, y, rx=r, ry=r, life=0.7, w=3)

    def rumble(self, x, y):
        """Rumbling energy: ゴゴゴゴ and wedges."""
        self.sfx("gogo", x, y, size=96, rot=rnd(-0.18, 0.1), life=1.0, style="hollow")
        self.ticks(x - 52, y + 8, dir=math.pi, n=3, r=6, len=14, life=0.5)

    def step(self, x, y, heading):
        """A footstep while walking: dust kicked back, the odd speed line."""
        back_dir = math.pi if heading > 0 else 0.0
        self.puff(x - heading * 10, y, size=rnd(5, 7), n=3, vx=-heading * rnd(16, 28), vy=-8, life=0.55)
        if random.random() < 0.5:
            self.lines(x - heading * 22, y - 18, n=2, dir=back_dir, len=26, spread=10, life=0.3)
