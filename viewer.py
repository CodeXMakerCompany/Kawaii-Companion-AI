"""Transparent Live2D desktop overlay for Linux/Wayland (layer-shell + EGL + Cubism SDK via live2d-py).

Controls
  left-drag on her  move her around the desktop
  arrows            drag the arrows on each side of her (shown on hover) to resize; she scales to fit
  scroll            zoom the model inside her area (R fits her to it again)
  hover             the model looks at the cursor
  Pendings button   open today's pending list above her head (she raises her right hand)
                    type + Enter adds, click toggles done, right-click deletes, Esc closes
  Talk button       she talks for 10 seconds (click again to stop early)
  Dance button      she dances on a beat until clicked again
  Pose button       she strikes 5 photo poses in a row (click again to stop)
  Walk / Greet      she strolls side to side (until clicked again) / bows and waves hello
  Calendar button   pick a date, type a title, Add reminder; on the day she nags until Done
  top-right pill    CPU/GPU/RAM at a glance; click for the full monitor (alarms nag until dismissed)
  mic / Alt+F10     voice commands: start/stop listening (voice-toggle.sh for a global shortcut)
  hotkeys           same expression keys as VTube Studio (Numpad1-9, 1-0, F1-F4)
  Backspace         clear expressions
  R                 fit her whole body to her area
  Esc               quit (position, size and zoom are saved)

Resource choices
  - Frame-capped loop that sleeps on the Wayland socket: no busy-wait, no vsync spin.
  - No MSAA, no depth/stencil, and only her area is drawn.
  - Uses the downscaled texture from build_model.py (2048px instead of 8192px).
  - The UI is painted once into a texture and only repainted when it changes.
  - Click effects (fx.py) are drawn only while one plays, cropped to what they cover, at 60 fps;
    --no-fx, or the desktop's animations switch, turns them off.
  - Transparent pixels are left out of the input region, so clicks there reach the desktop.
"""

import argparse
import contextlib
import datetime
import io
import json
import math
import os
import random
import signal
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("PYOPENGL_PLATFORM", "egl")  # must precede any OpenGL import

import numpy as np
import OpenGL
from OpenGL import EGL  # noqa: F401  PyOpenGL's EGL module breaks if imported after the next line

OpenGL.ERROR_CHECKING = False  # PyOpenGL checks glGetError after every GL call otherwise
from OpenGL import GL

with contextlib.redirect_stdout(io.StringIO()):  # live2d-py prints a banner on import
    import live2d

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))  # run.sh uses python -I, which leaves the script dir off sys.path
from fx import Effects, Press
from sysmon import SystemMonitor
from speech import Speaker
from voice import VoiceAssistant
from ui import NOTES_H, PANEL_W, Events, Overlay, Pendings
from wl_window import BTN_LEFT, BTN_RIGHT, LayerWindow

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "shark-viewer"
STATE_FILE = CONFIG_DIR / "state.json"
PENDINGS_FILE = CONFIG_DIR / "pendings.json"
EVENTS_FILE = CONFIG_DIR / "events.json"
ALERT_REPEAT = 180  # seconds between her reminders while something is waiting

# 比耶 (peace sign) pose: lifts her right hand to face height, the other arm stays down.
RAISE_HAND_PARAM = "Param77"
RAISE_HAND_SPEED = 8.0  # higher = faster blend

TALK_SECONDS = 10

# UI element kinds that react to a click (pointer cursor + hover highlight).
CLICKABLE = ("button", "item", "move", "moves_toggle", "action", "cal_prev", "cal_next", "cal_day", "cal_save",
             "cal_new", "cal_delete", "cal_event", "cal_done", "cal_yearly", "alert_action", "monitor_toggle",
             "mic", "voice_run", "voice_cancel")

MIN_MODEL, MAX_MODEL = (300, 360), (1600, 2200)  # her area, in px
SILHOUETTE_BAND = 24  # px; input-region rows follow her outline in bands this tall
SILHOUETTE_PAD = 14
FIT_PAD = 0.03  # space left around her when fitting, as a fraction of the area

# evdev key codes (layout independent, like VTube Studio's hotkeys)
KEY_ESC, KEY_BACKSPACE, KEY_ENTER, KEY_KPENTER, KEY_R, KEY_F10 = 1, 14, 28, 96, 19, 68
_KP = {1: 79, 2: 80, 3: 81, 4: 75, 5: 76, 6: 77, 7: 71, 8: 72, 9: 73, 0: 82}
_FKEYS = {1: 59, 2: 60, 3: 61, 4: 62, 5: 63, 6: 64, 7: 65, 8: 66, 9: 67, 10: 68, 11: 87, 12: 88}


def vtube_key_to_evdev(name):
    """VTube Studio trigger names -> evdev key codes ("Numpad1", "N1", "F1")."""
    if name.startswith("Numpad") and name[6:].isdigit():
        return _KP.get(int(name[6:]))
    if len(name) == 2 and name[0] == "N" and name[1].isdigit():
        return 11 if name[1] == "0" else 1 + int(name[1])
    if name[0] == "F" and name[1:].isdigit():
        return _FKEYS.get(int(name[1:]))
    return None


class TalkSimulator:
    """Fake speech for her mouth: syllables at roughly 5 per second, each opening by a
    different amount, with short pauses between words, then a smooth close."""

    def __init__(self):
        self.until = None  # talking ends at this time
        self.mouth = 0.0  # current ParamMouthOpenY (0..1)
        self.target = 0.0
        self.next_change = 0.0
        self.opening = False
        self.phase = 0.0  # head sway

    @property
    def active(self):
        return self.until is not None

    def start(self, now, seconds):
        self.until, self.next_change, self.opening = now + seconds, now, False

    def stop(self):
        self.until = None

    def seconds_left(self, now):
        return max(1, int(self.until - now + 0.999)) if self.active else None

    def update(self, now, dt):
        """Advance; returns (mouth, sway weight) while there is anything to apply, else None."""
        if self.active and now >= self.until:
            self.stop()
        if self.active and now >= self.next_change:
            self.opening = not self.opening
            if not self.opening and random.random() < 0.12:  # gap between words
                self.target, hold = 0.0, random.uniform(0.18, 0.35)
            elif self.opening:
                # her mouth is small: below ~0.5 it barely shows, so open wide
                self.target, hold = random.uniform(0.6, 1.0), random.uniform(0.07, 0.14)
            else:
                self.target, hold = random.uniform(0.0, 0.15), random.uniform(0.04, 0.08)
            self.next_change = now + hold
        if not self.active:
            self.target = 0.0
        self.mouth += (self.target - self.mouth) * min(1.0, dt * 22)
        self.phase += dt
        if not self.active and self.mouth < 0.01:
            return None
        return self.mouth, min(1.0, self.mouth * 2)


class Dancer:
    """A looping dance on a beat: side-to-side sway, a bounce and a nod on every beat, a
    head tilt, a new hand pose every 4 beats and a happy face. Hair and tail follow
    through the model's own physics. Eases in and out instead of snapping."""

    BPM = 118
    POSES = ("Param77", "Param78", "Param76", "Param79")  # peace sign, claws, finger heart, poke
    FACE = {"ParamEyeLSmile": 0.8, "ParamEyeRSmile": 0.8, "ParamMouthForm": 1.0, "ParamCheek": 0.6}
    BOUNCE = 0.02  # model offset units (half her area's height) at the top of each hop

    def __init__(self):
        self.active = False
        self.env = 0.0  # 0 = still, 1 = full dance
        self.beats = 0.0

    def toggle(self):
        self.active = not self.active
        if self.active and self.env == 0.0:
            self.beats = 0.0

    def update(self, dt):
        """Advance; returns {param: (value, weight)} and a bounce offset, or None when still."""
        self.env = min(1.0, self.env + dt / 0.6) if self.active else max(0.0, self.env - dt / 0.6)
        if self.env == 0.0:
            return None
        self.beats += dt * self.BPM / 60
        b, e = self.beats, self.env
        sway = math.sin(math.pi * b)  # one side per beat
        hop = abs(math.sin(math.pi * b))  # peaks between beats, lands on them
        nod = math.cos(2 * math.pi * b)
        params = {
            "ParamBodyAngleX": (9 * sway, e),
            "ParamBodyAngleZ": (-6 * sway, e),
            "ParamAngleX": (16 * sway, e),
            "ParamAngleY": (6 * nod, e),
            "ParamAngleZ": (9 * math.sin(math.pi * b / 2), e),
            "ParamEyeBallX": (-0.4 * sway, e),
        }
        params.update({p: (v, e) for p, v in self.FACE.items()})
        # Hand poses are art swaps, so crossfade quickly at each 4-beat boundary.
        seg, frac = divmod(b / 4, 1.0)
        now, prev = self.POSES[int(seg) % 4], self.POSES[int(seg - 1) % 4]
        blend = min(1.0, frac / 0.06)
        for p in self.POSES:
            params[p] = (1.0 if p == now else 0.0, e)
        if blend < 1.0 and prev != now:
            params[now], params[prev] = (blend, e), (1.0 - blend, e)
        return params, self.BOUNCE * hop * e


class PoseShow:
    """Five photo poses in a row: each blends in, holds, then gives way to the next;
    after the last she relaxes back. Every pose sets the same parameter set (missing
    ones fall back to NEUTRAL) so any two can be blended smoothly."""

    HOLD, BLEND = 2.6, 0.5  # seconds
    NEUTRAL = {
        "Param75": 0, "Param76": 0, "Param77": 0, "Param78": 0, "Param79": 0,  # hand poses
        "ParamBodyAngleX": 0, "ParamBodyAngleY": 0, "ParamBodyAngleZ": 0,
        "ParamAngleX": 0, "ParamAngleY": 0, "ParamAngleZ": 0,
        "ParamEyeLOpen": 1, "ParamEyeROpen": 1, "ParamEyeLSmile": 0, "ParamEyeRSmile": 0,
        "ParamEyeBallX": 0, "ParamEyeBallY": 0, "ParamBrowLY": 0, "ParamBrowRY": 0,
        "ParamBrowLAngle": 0, "ParamBrowRAngle": 0,
        "ParamMouthForm": 0, "ParamMouthOpenY": 0, "ParamCheek": 0, "Param13": 0, "Param67": 0,
    }
    POSES = [
        ("Wink", {"Param77": 1, "ParamAngleZ": 12, "ParamBodyAngleZ": -4, "ParamAngleX": 6,
                  "ParamEyeLOpen": 0, "ParamEyeRSmile": 0.5, "ParamMouthForm": 1, "ParamMouthOpenY": 0.25,
                  "Param67": 1, "ParamCheek": 0.6, "ParamBrowRY": 0.3}),
        ("Shoulder", {"ParamBodyAngleX": -10, "ParamBodyAngleZ": 3, "ParamAngleX": 24, "ParamAngleY": -6,
                      "ParamAngleZ": -6, "ParamEyeBallX": -0.7, "ParamEyeLOpen": 0.7, "ParamEyeROpen": 0.7,
                      "ParamMouthForm": 0.6, "Param13": 0.5, "ParamBrowLY": 0.2, "ParamBrowRY": 0.2}),
        ("Heart", {"Param76": 1, "ParamBodyAngleY": 8, "ParamAngleY": -4, "ParamAngleZ": -12,
                   "ParamEyeLSmile": 1, "ParamEyeRSmile": 1, "ParamMouthForm": 1, "ParamMouthOpenY": 0.4,
                   "ParamCheek": 0.9}),
        ("Thinking", {"Param79": 1, "ParamAngleZ": 10, "ParamAngleX": -8, "ParamBodyAngleZ": 4,
                      "ParamEyeBallY": 0.7, "ParamEyeBallX": 0.3, "ParamMouthForm": -0.4, "Param13": -0.4,
                      "ParamBrowLY": 0.4, "ParamBrowRY": 0.1, "ParamBrowLAngle": 0.3}),
        ("Rawr", {"Param78": 1, "ParamBodyAngleY": 6, "ParamBodyAngleZ": -5, "ParamAngleY": 8,
                  "ParamAngleZ": 6, "ParamMouthOpenY": 0.9, "ParamMouthForm": 0.3, "ParamBrowLY": -0.5,
                  "ParamBrowRY": -0.5, "ParamBrowLAngle": -0.6, "ParamBrowRAngle": -0.6, "ParamCheek": 0.4}),
    ]

    def __init__(self):
        self.t = None  # seconds into the show, None when not posing
        self.env = 0.0  # overall weight, eases in/out

    @property
    def active(self):
        return self.t is not None

    def toggle(self):
        self.t = None if self.active else 0.0

    def stop(self):
        self.t = None

    def label(self):
        if not self.active:
            return None
        i = min(len(self.POSES) - 1, int(self.t // self.HOLD))
        return f"{self.POSES[i][0]} {i + 1}/{len(self.POSES)}"

    def _pose(self, i):
        return {**self.NEUTRAL, **self.POSES[i][1]}

    def update(self, dt):
        """Advance; returns {param: (value, weight)} or None when she isn't posing."""
        if self.active:
            self.t += dt
            if self.t >= self.HOLD * len(self.POSES):
                self.stop()  # show over: relax back
        self.env = min(1.0, self.env + dt / self.BLEND) if self.active else max(0.0, self.env - dt / self.BLEND)
        if self.env == 0.0:
            return None
        t = min(self.t if self.active else self.HOLD * len(self.POSES) - 1e-6, self.HOLD * len(self.POSES) - 1e-6)
        i, into = divmod(t, self.HOLD)
        i = int(i)
        cur = self._pose(i)
        if i and into < self.BLEND:  # blend from the previous pose
            k = into / self.BLEND
            k = k * k * (3 - 2 * k)  # smoothstep
            prev = self._pose(i - 1)
            cur = {p: prev[p] + (cur[p] - prev[p]) * k for p in cur}
        return {p: (v, self.env) for p, v in cur.items()}


class Walker:
    """She strolls side to side across her area (or walks in place when it has no room),
    turned toward where she's going, with a bob on each step and a little hip sway."""

    STEPS_PER_SEC = 2.0
    LAP = 8.0  # seconds for there and back
    BOB = 0.012  # offset units at the top of a step

    def __init__(self):
        self.active = False
        self.env = 0.0
        self.t = 0.0

    def toggle(self):
        self.active = not self.active
        if self.active and self.env == 0.0:
            self.t = 0.0

    def stop(self):
        self.active = False

    def update(self, dt, room):
        """room: how far (offset units) she may stroll each way from her spot.
        Returns ({param: (value, weight)}, (dx, dy) offset) or None when still."""
        self.env = min(1.0, self.env + dt / 0.5) if self.active else max(0.0, self.env - dt / 0.5)
        if self.env == 0.0:
            return None
        self.t += dt
        e, s = self.env, self.t * self.STEPS_PER_SEC
        w = 2 * math.pi / self.LAP
        if room > 0.01:  # stroll: x follows a sine, she faces her velocity
            dx = room * math.sin(w * self.t)
            heading = math.cos(w * self.t)  # +1 = moving right
        else:  # no room: walk in place, looking one way then the other
            dx = 0.0
            heading = math.sin(w * self.t / 2)
        heading = max(-1.0, min(1.0, heading * 1.6))  # face the way for most of the lap
        step = abs(math.sin(math.pi * s))
        sway = math.sin(math.pi * s)
        params = {  # a positive body turn faces screen-left, hence the minus
            "ParamBodyAngleX": (-8 * heading, e),
            "ParamAngleX": (-18 * heading, e),
            "ParamEyeBallX": (0.5 * heading, e),
            "ParamBodyAngleZ": (3 * sway, e),
            "ParamAngleZ": (-2 * sway, e),
            "ParamAngleY": (3 * math.cos(2 * math.pi * s), e),
            "ParamMouthForm": (0.5, e),
        }
        return params, (dx * e, self.BOB * step * e)


class Greeter:
    """A one-shot hello: a small bow, then upright with a big smile, hand raised and
    waving while she says 'hi', then she relaxes."""

    LENGTH = 4.5
    WAVE_HANDS = ("Param77", "Param79")  # two raised-hand drawings swapped quickly = a wave

    def __init__(self):
        self.t = None
        self.env = 0.0

    @property
    def active(self):
        return self.t is not None

    def toggle(self):
        self.t = None if self.active else 0.0

    def stop(self):
        self.t = None

    def update(self, dt):
        """Returns {param: (value, weight)} or None when she isn't greeting."""
        if self.active:
            self.t += dt
            if self.t >= self.LENGTH:
                self.stop()
        self.env = min(1.0, self.env + dt / 0.3) if self.active else max(0.0, self.env - dt / 0.4)
        if self.env == 0.0:
            return None
        t, e = (self.t if self.active else self.LENGTH), self.env

        def ramp(a, b):  # 0 before a, 1 after b, smooth in between
            k = min(1.0, max(0.0, (t - a) / (b - a)))
            return k * k * (3 - 2 * k)

        bow = ramp(0.0, 0.5) * (1 - ramp(0.8, 1.3))  # down and back up
        wave = ramp(1.1, 1.4) * (1 - ramp(3.9, self.LENGTH))
        rock = math.sin(2 * math.pi * 2.5 * t) * wave
        flip = int(t / 0.18) % 2  # which hand drawing this instant
        talk = wave * max(0.0, math.sin(2 * math.pi * 2.2 * (t - 1.4))) * (t < 2.9)  # "hi! hel-lo!"
        params = {
            "ParamAngleY": (-14 * bow + 4 * wave, e),
            "ParamBodyAngleY": (7 * bow, e),
            "ParamAngleZ": (7 * rock, e),
            "ParamBodyAngleZ": (2.5 * rock, e),
            "ParamEyeLSmile": (1.0 * max(bow, wave), e),
            "ParamEyeRSmile": (1.0 * max(bow, wave), e),
            "ParamMouthForm": (1.0, e),
            "ParamMouthOpenY": (0.8 * talk, e),
            "ParamCheek": (0.5 * wave, e),
            self.WAVE_HANDS[0]: (wave * (1 - flip), e),
            self.WAVE_HANDS[1]: (wave * flip, e),
        }
        return params


class OverlayTexture:
    """A UI layer as one GL texture, blended over the model with a single quad (the whole
    window by default, or a small rectangle such as the system monitor)."""

    def __init__(self, w, h):
        self.tex = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.tex)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_NEAREST)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_NEAREST)
        self.resize(w, h)

    def resize(self, w, h):
        self.w, self.h = w, h
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.tex)
        GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA8, w, h, 0, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, None)

    def upload(self, data, fmt=GL.GL_RGBA):
        """fmt: GL_BGRA for cairo surfaces (premultiplied too)."""
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.tex)
        GL.glTexSubImage2D(GL.GL_TEXTURE_2D, 0, 0, 0, self.w, self.h, fmt, GL.GL_UNSIGNED_BYTE, data)

    def draw(self, x=0, y=0, window_h=None):
        """x, y: top-left in window coords (window_h needed to flip to GL's bottom-left)."""
        # Cubism leaves its shader/buffers bound; reset to plain fixed-function state.
        GL.glUseProgram(0)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, 0)
        GL.glViewport(int(x), int((window_h - y - self.h) if window_h else 0), self.w, self.h)
        for cap in (GL.GL_CULL_FACE, GL.GL_DEPTH_TEST, GL.GL_STENCIL_TEST, GL.GL_SCISSOR_TEST):
            GL.glDisable(cap)
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_ONE, GL.GL_ONE_MINUS_SRC_ALPHA)  # texture is premultiplied
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glEnable(GL.GL_TEXTURE_2D)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.tex)
        GL.glColor4f(1, 1, 1, 1)
        GL.glBegin(GL.GL_QUADS)  # rows are top-down, so v=0 is the top edge
        GL.glTexCoord2f(0, 1); GL.glVertex2f(-1, -1)
        GL.glTexCoord2f(1, 1); GL.glVertex2f(1, -1)
        GL.glTexCoord2f(1, 0); GL.glVertex2f(1, 1)
        GL.glTexCoord2f(0, 0); GL.glVertex2f(-1, 1)
        GL.glEnd()
        GL.glDisable(GL.GL_TEXTURE_2D)


def read_alpha(left, model_w, model_h):
    """Her coverage mask (rows top-down) from the frame just drawn; model pixels only."""
    data = GL.glReadPixels(left, 0, model_w, model_h, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
    return np.frombuffer(data, np.uint8).reshape(model_h, model_w, 4)[::-1, :, 3] > 8


def silhouette_rects(alpha, left):
    """Row bands (window coords) around her outline, for the input region."""
    model_h, model_w = alpha.shape
    rects = []
    for y0 in range(0, model_h, SILHOUETTE_BAND):
        cols = np.flatnonzero(alpha[y0:y0 + SILHOUETTE_BAND].any(axis=0))
        if cols.size:
            x0 = max(0, cols[0] - SILHOUETTE_PAD)
            x1 = min(model_w, cols[-1] + 1 + SILHOUETTE_PAD)
            rects.append((left + x0, NOTES_H + y0, x1 - x0, min(SILHOUETTE_BAND, model_h - y0)))
    return rects


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


def replace_running_copy(timeout=4.0):
    """Ask any other running copy of this viewer to quit (it saves and exits cleanly on
    SIGTERM), so starting her again always gives exactly one, up-to-date, overlay."""
    me = os.getpid()
    others = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) == me:
            continue
        try:
            cmd = (entry / "cmdline").read_bytes().split(b"\0")
            same_app = any(arg.endswith(b"viewer.py") for arg in cmd) and Path(os.readlink(entry / "cwd")) == HERE
        except OSError:
            continue
        if same_app and b"--snapshot" not in cmd and b"--allow-multiple" not in cmd:
            others.append(int(entry.name))
    for pid in others:
        with contextlib.suppress(OSError):
            os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + timeout
    while others and time.monotonic() < deadline:
        others = [pid for pid in others if Path(f"/proc/{pid}").exists()]
        time.sleep(0.05)
    for pid in others:  # an old build without the SIGTERM handler, or stuck
        with contextlib.suppress(OSError):
            os.kill(pid, signal.SIGKILL)


def animations_enabled():
    """The desktop's reduce-motion switch (GNOME's enable-animations); on when unknown."""
    try:
        out = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", "enable-animations"],
                             capture_output=True, text=True, timeout=2)
    except (OSError, subprocess.SubprocessError):
        return True
    return out.stdout.strip() != "false"


def is_portrait(output):
    return bool(output and output.h > output.w)


def load_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except (OSError, ValueError):
        return {}


def save_state(state):
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, indent=1))
    except OSError:
        pass


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", type=Path, default=HERE / "model" / "model.model3.json")
    ap.add_argument("--size", help="her area WxH on wide screens (default: last used, else 420x620)")
    ap.add_argument("--fps", type=float, default=30, help="frame cap (default 30)")
    ap.add_argument("--scale", type=float, help="fixed model zoom instead of fitting her to the area")
    ap.add_argument("--pendings", action="store_true", help="start with the Pendings list open")
    ap.add_argument("--no-fx", action="store_true",
                    help="no sakuga effects on clicks (also off when the desktop turns animations off)")
    ap.add_argument("--snapshot", type=Path, help="render ~2.5s, save a PNG with alpha and exit")
    ap.add_argument("--allow-multiple", action="store_true", help="keep other running copies instead of replacing them")
    return ap.parse_args()


def clamp_size(w, h):
    return (int(min(MAX_MODEL[0], max(MIN_MODEL[0], w))), int(min(MAX_MODEL[1], max(MIN_MODEL[1], h))))


def main():
    args = parse_args()
    if not (args.snapshot or args.allow_multiple):
        replace_running_copy()  # before reading state, so the old copy's last save is included
    state = load_state()
    layouts = state.setdefault("layouts", {})  # per monitor name: margin, model_size, scale, offset
    default_size = clamp_size(*(int(v) for v in args.size.lower().split("x"))) if args.size else (420, 620)
    saved = layouts.get(state.get("output"), {})
    model_w, model_h = saved.get("model_size", default_size)
    left = saved.get("left", PANEL_W)

    win = LayerWindow(left + model_w, NOTES_H + model_h, saved.get("margin", [80, 80]),
                      output_name=state.get("output"))

    live2d.enableLog(False)
    live2d.init()
    live2d.glInit()
    model = live2d.Model()
    model.LoadModelJson(str(args.model))
    model.Resize(model_w, model_h)
    model.SetAutoBlink(True)
    model.SetAutoBreath(True)

    hotkeys = {}
    hotkeys_file = args.model.parent / "hotkeys.json"
    if hotkeys_file.exists():
        for trigger, exp in json.loads(hotkeys_file.read_text()).items():
            key = vtube_key_to_evdev(trigger)
            if key is not None:
                hotkeys[key] = exp
    active = set()

    pendings = Pendings(PENDINGS_FILE)
    events = Events(EVENTS_FILE)
    monitor = SystemMonitor()
    assistant = VoiceAssistant(HERE, CONFIG_DIR)
    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    cache_home = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    speaker = Speaker(data_home / "shark-viewer" / "kokoro", cache_home / "shark-viewer" / "tts", HERE / "voice_lines.json")
    if not args.snapshot:
        speaker.prerender()  # her fixed lines, generated once in the background
    talker = TalkSimulator()
    dancer = Dancer()
    poser = PoseShow()
    walker = Walker()
    greeter = Greeter()
    routines = (dancer, poser, walker, greeter)  # each drives her whole body: one at a time
    moves_file = HERE / "moves.json"  # labelled, grouped mini buttons; falls back to raw names
    if moves_file.exists():
        move_groups = json.loads(moves_file.read_text(encoding="utf-8"))["groups"]
    else:
        move_groups = [{"name": "Moves", "moves": [[exp, exp] for exp in sorted(set(hotkeys.values()))]}]
    overlay = Overlay(model_w, model_h, 1.0, left)
    overlay.moves = move_groups
    overlay_tex = OverlayTexture(win.width, win.height)
    monitor_tex = OverlayTexture(1, 1)  # the monitor's own small layer: its numbers change every 2s
    effects = Effects(enabled=not args.no_fx and animations_enabled())
    fx_tex = OverlayTexture(1, 1)  # the effects' layer, only drawn while one is alive
    presses = {}  # (kind, name) -> Press, for buttons springing back from a click
    after_paint = []  # effects placed by the next repaint's layout (the caret, a new bubble)

    view = {
        "left": left,  # button column width: PANEL_W on wide screens, 0 on portrait ones
        "size": (model_w, model_h),  # her area
        "pending_geometry": None,  # (left, top, w, h) to apply at the next frame
        "scale": 1.0,
        "offset": (0.0, 0.0),
        "fit_due": None,  # time of the next auto-fit pass
        "fit_passes": 0,
        "layout_output": None,  # monitor name the current layout belongs to
        "open": args.pendings,  # Pendings feature on
        "cal_open": False,  # calendar card
        "cal_month": (datetime.date.today().year, datetime.date.today().month),
        "cal_selected": datetime.date.today().isoformat(),
        "cal_draft": "",
        "cal_editing": None,  # id of the reminder being edited
        "cal_yearly": False,  # Yearly switch for the reminder being added/edited
        "alert_ids": set(),  # alerts already announced
        "next_nag": None,  # when she reminds again
        "next_alert_check": 0.0,
        "mon_open": state.get("monitor_open", False),
        "voice_text": None,  # banner text
        "voice_error": False,
        "voice_command": None,  # AI suggestion waiting for Run/Cancel
        "voice_until": None,  # hide the banner after this time
        "voice_heard": "",
        "voice_toggle": False,  # set by SIGUSR1 (global shortcut script)
        "voice_dance": False,  # True while she dances because a voice command is being processed
        "mon_key": None,  # last monitor view, to repaint only on change
        "mon_shape": None,  # what the monitor's click areas depend on (open, rows)
        "mon_dirty": True,
        "mon_pos": (0, 0),
        "moves_open": state.get("moves_open", True),  # mini move buttons expanded
        "draft": "",
        "hand": 0.0,  # current raise-hand blend weight
        "dirty": True,  # overlay needs repainting
        "mouse": (-1.0, -1.0),
        "drag": None,  # {"kind", "press", ...} while moving or resizing
        "silhouette": None,  # input-region bands around her, from a readback
        "body_box": None,  # her left/right extent in her area (px), from the same readback
        "was_moving": False,
        "silhouette_due": None,
        "region_dirty": True,
        "flash_until": None,  # end of a button's inverted impact frame
        "pose_seen": None,  # last pose label, to flash on each new pose
        "next_pulse": 0.0,  # mic ring while listening
        "next_rumble": 0.0,  # ゴゴゴゴ while dancing
        "next_step": 0.0,  # dust while walking
        "walk_x": 0.0,
        "banner_shown": False,
    }

    def set_transform(scale, offset):
        view["scale"], view["offset"] = scale, tuple(offset)
        model.SetScale(scale)
        model.SetOffset(*offset)

    def refresh_silhouette(delay=0.35):
        view["silhouette_due"] = time.perf_counter() + delay

    def request_fit(delay=0.15):
        if args.scale:
            set_transform(args.scale, (0.0, 0.0))
            refresh_silhouette()
            return
        view["fit_due"] = time.perf_counter() + delay
        view["fit_passes"] = 0

    def remember_layout():
        """Store and save this monitor's layout right away, so a crash or kill never loses it."""
        if win.output and not args.snapshot:
            layouts[win.output.name] = {"margin": list(win.margin), "model_size": list(view["size"]),
                                        "left": view["left"], "scale": float(view["scale"]),
                                        "offset": [float(v) for v in view["offset"]]}
            state["output"] = win.output.name
            save_state(state)

    def apply_layout(output):
        """Switch to `output`'s remembered layout, or a fresh one that suits its shape."""
        view["layout_output"] = output.name if output else None
        saved = layouts.get(output.name) if output else None
        if saved:
            view["left"] = saved.get("left", PANEL_W)
            mw, mh = saved["model_size"]
            margin = saved["margin"]
            set_transform(saved.get("scale", 1.0), saved.get("offset", (0.0, 0.0)))
            refresh_silhouette(0.2)
        elif is_portrait(output):  # tall screen: fill it, buttons float beside her head
            view["left"] = 0
            mw, mh, margin = output.w, output.h - NOTES_H, (0, 0)
            request_fit()
        else:
            view["left"] = PANEL_W
            (mw, mh), margin = default_size, win.margin
            request_fit()
        view["pending_geometry"] = (*margin, view["left"] + mw, NOTES_H + mh)

    def toggle_move(exp):
        """VTube Studio style ToggleExpression; None clears them all. Shared by keys and mini buttons."""
        if exp is None:
            model.ResetExpressions()
            active.clear()
        elif exp in active:
            model.RemoveExpression(exp)
            active.discard(exp)
        else:
            model.AddExpression(exp)
            active.add(exp)
        view["dirty"] = True
        refresh_silhouette(0.6)  # poses, chibi and outfit change her outline

    def toggle_routine(routine):
        for other in routines:
            if other is not routine and other.active:
                other.toggle()  # toggling an active routine stops it
        routine.toggle()
        view["dirty"] = True
        view["region_dirty"] = True

    def set_open(on):
        if on:
            pendings.roll_day()
            view["cal_open"] = False  # one card at a time
        view["open"] = on
        view["dirty"] = True
        refresh_silhouette(0.7)  # after the hand has finished moving

    def set_calendar(on):
        if on:
            set_open(False)
            today = datetime.date.today()
            if not view["cal_editing"]:
                view["cal_month"], view["cal_selected"] = (today.year, today.month), today.isoformat()
        view["cal_open"] = on
        view["dirty"] = True
        view["next_alert_check"] = 0.0

    def save_reminder():
        title = view["cal_draft"].strip()
        if not title:
            return
        if view["cal_editing"]:
            events.update(view["cal_editing"], view["cal_selected"], title, view["cal_yearly"])
        else:
            events.add(view["cal_selected"], title, view["cal_yearly"])
        view["cal_draft"], view["cal_editing"], view["cal_yearly"] = "", None, False
        view["dirty"] = True
        view["next_alert_check"] = 0.0

    def edit_reminder(event_id):
        e = events.get(event_id)
        if e:
            day = datetime.date.fromisoformat(e["date"])
            view.update(cal_editing=event_id, cal_selected=e["date"], cal_month=(day.year, day.month),
                        cal_draft=e["title"], cal_yearly=e["yearly"], dirty=True)

    def alerts():
        """Waiting bubbles: due reminders first (oldest first), then system alarms."""
        today = datetime.date.today()
        out = []
        for e in events.due(today):
            day = events.when(e, today)
            label = "REMINDER · TODAY" if day == today else f"OVERDUE · {day.strftime('%a %d %b').upper()}"
            label += " · YEARLY" if e["yearly"] else ""
            out.append({"id": "ev:" + e["id"], "label": label, "title": e["title"], "action": "Done"})
        for name, message in monitor.alarms:
            out.append({"id": "sys:" + name, "label": "SYSTEM ALARM", "title": message, "action": "Dismiss"})
        return out

    def handle_alert(alert_id):
        kind, _, key = alert_id.partition(":")
        if kind == "ev":
            events.toggle_done(key)
        else:
            monitor.snooze(key)
        view["dirty"] = True
        view["next_alert_check"] = 0.0

    def nag():
        """Get attention: a greeting (unless she is busy with another routine) and she says
        what is waiting (the first reminder or alarm)."""
        if not any(r.active for r in routines):
            toggle_routine(greeter)
        waiting = alerts()
        said = None
        if waiting:
            first = waiting[0]
            if first["id"].startswith("ev:"):
                today = first["label"].startswith("REMINDER")
                said = speaker.react("reminder_today" if today else "reminder_overdue", title=first["title"])
            else:
                kind = first["id"][4:].split(":")[0]
                said = speaker.lines.get("alarms", {}).get(kind)
                if said:
                    speaker.say(said)
        if not (said and speaker.available):
            talker.start(time.perf_counter(), 3)  # no voice: at least move her mouth
        bubble = overlay.rect_of("alert") or overlay.rect_of("monitor_toggle")
        if bubble:
            effects.nudge(bubble)
        view["dirty"] = True

    def head():
        """Top centre of her (window coords), for effects on her."""
        box, (mw, _) = view["body_box"], view["size"]
        x = view["left"] + ((box[0] + box[1]) / 2 if box else mw / 2)
        return x, overlay.head_y if overlay.head_y is not None else NOTES_H + 16

    def impact_frame(hit):
        """The button turns inside out for an instant, then springs back."""
        overlay.flash = hit
        view["flash_until"] = time.perf_counter() + 0.19

    def look_at(x, y):
        mw, mh = view["size"]
        mx, my = x - view["left"], y - NOTES_H
        if 0 <= mx < mw and 0 <= my < mh:
            model.Drag(mx, my)
        else:
            model.Drag(mw / 2, mh / 2)

    def cursor_for(hit):
        if view["drag"]:
            return {"move": "grabbing", "left": "ew_resize", "right": "ew_resize"}.get(view["drag"]["kind"], "ns_resize")
        if hit and hit[0] == "handle":
            return "ew_resize" if hit[1] in ("left", "right") else "ns_resize"
        if hit and hit[0] in CLICKABLE:
            return "pointer"
        if hit and hit[0] == "cal_input":
            return "text"
        return "default"

    def on_motion(x, y):
        view["mouse"] = (x, y)
        drag = view["drag"]
        if drag:
            # Pointer coords are surface-local and the surface itself moves, so work in
            # output coords (applied margin + local) relative to where the press happened.
            (px, py), (sl, st), (sw, sh) = drag["press"], drag["margin"], drag["start"]
            dx = win.margin[0] + x - (sl + px)
            dy = win.margin[1] + y - (st + py)
            kind = drag["kind"]
            if kind == "move":  # in desktop coords, so she can cross onto another monitor
                gx, gy = win.local_to_global(x, y)
                (gpx, gpy), (gtx, gty) = drag["g_press"], drag["g_topleft"]
                win.place(gtx + gx - gpx, gty + gy - gpy, gx, gy)
                return
            left, top, mw, mh = sl, st, sw, sh
            if kind == "right":
                mw = sw + dx
            elif kind == "bottom":
                mh = sh + dy
            elif kind == "left":
                mw = clamp_size(sw - dx, sh)[0]
                left = sl + (sw - mw)
            elif kind == "top":
                mh = clamp_size(sw, sh - dy)[1]
                top = st + (sh - mh)
            mw, mh = clamp_size(mw, mh)
            view["pending_geometry"] = (max(0, int(left)), max(0, int(top)), view["left"] + mw, NOTES_H + mh)
            return

        look_at(x, y)
        hit = overlay.hit(x, y)
        hover = hit if hit and (hit[0] in CLICKABLE or hit[0] == "handle") else None
        if hover != overlay.hover or not overlay.show_handles:
            overlay.hover = hover
            overlay.show_handles = True
            view["dirty"] = True
        win.set_cursor(cursor_for(hit))

    def on_leave():
        if view["drag"]:
            return
        look_at(-1, -1)
        if overlay.hover or overlay.show_handles:
            overlay.hover = None
            overlay.show_handles = False
            view["dirty"] = True

    def on_button(button, pressed):
        x, y = view["mouse"]
        if not pressed:
            if view["drag"]:
                resized = view["drag"]["kind"] != "move"
                view["drag"] = None
                if resized:
                    request_fit()  # refit her to the new area
                else:
                    refresh_silhouette()
                remember_layout()
                win.set_cursor(cursor_for(overlay.hit(x, y)))
            return
        hit = overlay.hit(x, y)
        rect = overlay.rect_of(*hit) if hit else None
        if hit and hit[0] in ("button", "action", "move") and button == BTN_LEFT:
            presses[hit] = Press()
        if hit == ("button", "pendings") and button == BTN_LEFT:
            set_open(not view["open"])
            if view["open"]:
                effects.pop(rect)
            else:
                effects.poof(rect[2] - 16, (rect[1] + rect[3]) / 2)
        elif hit == ("button", "calendar") and button == BTN_LEFT:
            set_calendar(not view["cal_open"])
            if view["cal_open"]:
                effects.pop(rect)
            else:
                effects.poof(rect[2] - 16, (rect[1] + rect[3]) / 2)
        elif hit and hit[0] in ("cal_prev", "cal_next") and button == BTN_LEFT:
            y_, m_ = view["cal_month"]
            m_ += -1 if hit[0] == "cal_prev" else 1
            view["cal_month"] = (y_ + (m_ - 1) // 12, (m_ - 1) % 12 + 1)
            view["dirty"] = True
        elif hit and hit[0] == "cal_day" and button == BTN_LEFT:
            view["cal_selected"] = hit[1]
            day = datetime.date.fromisoformat(hit[1])
            view["cal_month"] = (day.year, day.month)  # clicking a greyed day jumps to its month
            view["dirty"] = True
            effects.pick(rect)
        elif hit == ("cal_save", None) and button == BTN_LEFT:
            if view["cal_draft"].strip():
                effects.tap(rect)
            save_reminder()
        elif hit == ("cal_new", None) and button == BTN_LEFT:
            view.update(cal_editing=None, cal_draft="", cal_yearly=False, dirty=True)
        elif hit == ("cal_yearly", None) and button == BTN_LEFT:
            view.update(cal_yearly=not view["cal_yearly"], dirty=True)
        elif hit == ("cal_delete", None) and button == BTN_LEFT:
            effects.scrap(rect)
            events.remove(view["cal_editing"])
            view.update(cal_editing=None, cal_draft="", cal_yearly=False, dirty=True, next_alert_check=0.0)
        elif hit and hit[0] == "cal_done" and button == BTN_LEFT:
            events.toggle_done(hit[1])
            view.update(dirty=True, next_alert_check=0.0)
            cx, cy = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
            if events.is_done(events.get(hit[1])):
                effects.check(cx, cy)
            else:
                effects.poof(cx, cy)
        elif hit and hit[0] == "cal_event":
            if button == BTN_LEFT:
                edit_reminder(hit[1])
            elif button == BTN_RIGHT:
                effects.scrap(rect)
                events.remove(hit[1])
                if view["cal_editing"] == hit[1]:
                    view.update(cal_editing=None, cal_draft="")
                overlay.hover = None
                view.update(dirty=True, next_alert_check=0.0)
        elif hit and hit[0] == "alert_action" and button == BTN_LEFT:
            effects.tap(rect)
            handle_alert(hit[1])
        elif hit == ("mic", None) and button == BTN_LEFT:
            assistant.toggle()
            view["next_pulse"] = 0.0
        elif hit and hit[0] in ("voice_run", "voice_cancel") and button == BTN_LEFT:
            if hit[0] == "voice_run":
                effects.impact(rect)
            else:
                effects.poof((rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2)
            assistant.confirm(hit[0] == "voice_run")
        elif hit == ("monitor_toggle", None) and button == BTN_LEFT:
            view["mon_open"] = not view["mon_open"]
            state["monitor_open"] = view["mon_open"]
            save_state(state)
            view.update(mon_key=None, dirty=True)
            if view["mon_open"]:  # the panel's size is known once it is painted
                after_paint.append(lambda: overlay.rect_of("monitor_panel") and effects.bubble(
                    overlay.rect_of("monitor_panel"), overlay.rect_of("monitor_toggle")))
            else:
                effects.poof(rect[0] + 14, (rect[1] + rect[3]) / 2)
        elif hit in (("button", "dance"), ("button", "pose"), ("action", "walk"), ("action", "greet")) \
                and button == BTN_LEFT:
            routine = {"dance": dancer, "pose": poser, "walk": walker, "greet": greeter}[hit[1]]
            toggle_routine(routine)
            if hit[1] == "greet" and greeter.active:
                speaker.react("greet")
            if not routine.active:
                effects.poof(rect[2] - 12, (rect[1] + rect[3]) / 2)
            elif hit[1] == "dance":
                impact_frame(hit)
                effects.impact(rect)
            elif hit[1] == "pose":
                effects.pick(rect)  # each pose then flashes as it comes up
            elif hit[1] == "walk":
                effects.pick(rect)
                effects.stride(head()[0], win.height - 24)
            else:
                effects.pick(rect)
                effects.hello(*head())
        elif hit == ("button", "talk") and button == BTN_LEFT:
            if talker.active:
                talker.stop()
                effects.poof(rect[2] - 12, (rect[1] + rect[3]) / 2)
            else:
                talker.start(time.perf_counter(), TALK_SECONDS)
                effects.chatter(*head())
            view["dirty"] = True
        elif hit and hit[0] == "move" and button == BTN_LEFT:
            if hit[1] is None:  # Clear all: a puff off every move that was on
                for exp in active:
                    r = overlay.rect_of("move", exp)
                    if r:
                        effects.poof((r[0] + r[2]) / 2, (r[1] + r[3]) / 2, size=5)
            elif hit[1] in active:
                effects.poof(rect[2] - 8, (rect[1] + rect[3]) / 2, size=5)
            else:
                effects.pick(rect)
            toggle_move(hit[1])
        elif hit and hit[0] == "moves_toggle" and button == BTN_LEFT:
            view["moves_open"] = not view["moves_open"]
            state["moves_open"] = view["moves_open"]
            save_state(state)
            overlay.hover = None
            view["dirty"] = True
        elif hit and hit[0] == "item":
            box = (rect[0] + 21.5, rect[1] + 11.5)  # its checkbox
            if button == BTN_LEFT:
                pendings.toggle(hit[1])
                if pendings.items[hit[1]]["done"]:
                    effects.check(*box)
                else:
                    effects.poof(*box)
            elif button == BTN_RIGHT:
                effects.scrap(rect)
                pendings.remove(hit[1])
                overlay.hover = None
            view["dirty"] = True
        elif hit and hit[0] in ("card", "cal_card", "cal_input", "alert", "monitor_panel", "voice_banner"):
            pass  # clicking a card just keeps keyboard focus here (no drag)
        elif button == BTN_LEFT:
            kind = hit[1] if hit and hit[0] == "handle" else "move"
            view["drag"] = {"kind": kind, "press": (x, y), "start": view["size"], "margin": tuple(win.margin),
                            "g_press": win.local_to_global(x, y), "g_topleft": win.local_to_global(0, 0)}
            win.set_cursor(cursor_for(hit))

    def on_scroll(steps):  # manual zoom around her centre; R refits
        set_transform(min(5.0, max(0.2, view["scale"] * (1.1 ** steps))), view["offset"])
        refresh_silhouette()
        remember_layout()

    def on_text(text):
        if view["cal_open"]:
            view["cal_draft"] += text
            view["dirty"] = True
        elif view["open"]:
            view["draft"] += text
            view["dirty"] = True
        else:
            return
        after_paint.append(lambda: overlay.caret and effects.dust(*overlay.caret))  # where the caret moved to

    def on_key(key, pressed):
        if not pressed:
            return
        if key == KEY_F10 and win.xkb.alt():  # voice: start / stop listening
            assistant.toggle()
            return
        if view["cal_open"]:  # typing a reminder title: Enter saves, Esc closes
            if key == KEY_ESC:
                set_calendar(False)
            elif key in (KEY_ENTER, KEY_KPENTER):
                if view["cal_draft"].strip() and overlay.rect_of("cal_save"):
                    effects.tap(overlay.rect_of("cal_save"))
                save_reminder()
            elif key == KEY_BACKSPACE and view["cal_draft"]:
                if win.xkb.ctrl():
                    view["cal_draft"] = view["cal_draft"].rstrip().rpartition(" ")[0]
                else:
                    view["cal_draft"] = view["cal_draft"][:-1]
                view["dirty"] = True
            return
        if view["open"]:  # typing into the list: no hotkeys, Esc just closes it
            if key == KEY_ESC:
                set_open(False)
            elif key in (KEY_ENTER, KEY_KPENTER):
                text = view["draft"].strip()
                if text:
                    pendings.add(text)
                    new = len(pendings.items) - 1
                    after_paint.append(lambda: overlay.rect_of("item", new) and effects.done(overlay.rect_of("item", new)))
                view["draft"] = ""
                view["dirty"] = True
            elif key == KEY_BACKSPACE and view["draft"]:
                if win.xkb.ctrl():  # delete last word
                    view["draft"] = view["draft"].rstrip().rpartition(" ")[0]
                else:
                    view["draft"] = view["draft"][:-1]
                view["dirty"] = True
            return

        if key == KEY_ESC:  # the only quit key, shown in the footer
            win.closed = True
        elif key == KEY_BACKSPACE:
            toggle_move(None)
        elif key == KEY_R:
            request_fit(0.0)
        elif key in hotkeys:  # VTube Studio "ToggleExpression"
            toggle_move(hotkeys[key])

    def on_surface_changed():
        # A new surface starts with a full input region: resend ours.
        view["region_dirty"] = True
        name = win.output.name if win.output else None
        if name != view["layout_output"]:  # arrived on another monitor (or learned which one)
            apply_layout(win.output)
        elif (win.width - view["left"], win.height - NOTES_H) != view["size"]:  # shrunk to fit it
            view["pending_geometry"] = (*win.margin, win.width, win.height)

    win.on_motion, win.on_leave, win.on_button = on_motion, on_leave, on_button
    win.on_scroll, win.on_text, win.on_key = on_scroll, on_text, on_key
    win.on_surface_changed = on_surface_changed

    # Ctrl+C, kill and a closing terminal all end the loop normally (state saved, GL torn
    # down in order) instead of dying mid-frame.
    def request_quit(signum, frame):
        win.closed = True

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, request_quit)
    signal.signal(signal.SIGUSR1, lambda signum, frame: view.update(voice_toggle=True))

    if win.output:
        apply_layout(win.output)
    else:
        request_fit(0.3)

    last = next_frame = time.perf_counter()
    snapshot_at = last + 2.5 if args.snapshot else None

    while not win.closed:
        now = time.perf_counter()
        if now < next_frame:
            win.pump(next_frame - now)
            continue
        # Smooth 60 fps while being dragged or resized, the normal cap otherwise.
        frame = 1.0 / (max(args.fps, 60) if view["drag"] or effects.busy else args.fps)
        next_frame += frame
        if next_frame < now:  # fell behind (suspend, stall): resync instead of bursting
            next_frame = now + frame
        dt = now - last
        last = now

        geometry = view["pending_geometry"]
        if geometry:  # coalesced resize: one relayout per frame however fast the pointer moves
            view["pending_geometry"] = None
            win.set_geometry(*geometry)
            mw, mh = win.width - view["left"], win.height - NOTES_H  # the window may cap it to the monitor
            if (mw, mh) != view["size"] or overlay.left != view["left"]:
                view["size"] = (mw, mh)
                model.Resize(mw, mh)
                set_transform(view["scale"], view["offset"])
                overlay.resize(mw, mh, view["left"])
                overlay_tex.resize(win.width, win.height)
                view["dirty"] = True
                refresh_silhouette()

        if model.IsMotionFinished():
            model.StartRandomMotion("Idle", live2d.MotionPriority.IDLE)
        model.Update(dt)
        # Ease the raised hand in/out; only touch the parameter while it is in use.
        target = 1.0 if view["open"] else 0.0
        view["hand"] += (target - view["hand"]) * min(1.0, dt * RAISE_HAND_SPEED)
        # Voice: apply what the worker reported; she says it out loud when a command runs.
        if view["voice_toggle"]:
            view["voice_toggle"] = False
            assistant.toggle()
        assistant.tick()
        for ev in assistant.poll():
            kind = ev[0]
            meta = ev[-1] if isinstance(ev[-1], dict) else {}
            view.update(voice_error=False, voice_command=None, voice_until=None, dirty=True)
            if assistant.state == "listening":
                speaker.stop()  # never record her own voice
            if kind == "status":
                view["voice_text"] = ev[1]
                if meta.get("kind") == "cancelled":
                    speaker.react("cancelled")
            elif kind == "heard":
                view["voice_heard"] = ev[1]
                view["voice_text"] = f"\u201c{ev[1]}\u201d"
            elif kind == "run":
                view["voice_text"] = f"\u201c{view['voice_heard']}\u201d: {ev[2]}  ($ {ev[1]})"
                view["voice_until"] = now + 6
                if meta.get("kind") in ("open", "close"):
                    speaker.react(meta["kind"], app=meta.get("app"))
                else:  # learned/AI commands: their "say" may be in another language than her voice
                    speaker.react("ran")
                if not speaker.available:
                    talker.start(now, 2)
            elif kind == "confirm":
                view["voice_text"] = f"AI suggests for \u201c{view['voice_heard']}\u201d: {ev[2]}".rstrip(": ")
                view["voice_command"] = ev[1]
                speaker.react("confirm_ai")  # "I found this command. Wanna check it first?"
                if not speaker.available:
                    talker.start(now, 1.5)
            elif kind == "error":
                view.update(voice_text=ev[1], voice_error=True, voice_until=now + 6)
                if meta.get("kind") in ("not_open", "open_failed", "ai_failed", "refused", "not_heard",
                                        "no_command", "ai_down"):
                    speaker.react(meta["kind"], app=meta.get("app"))
            elif kind == "learned":  # an approved AI command worked and is now a regular command
                view.update(voice_text=f"Learned \u201c{ev[1]}\u201d: saved to commands.json", voice_until=now + 6)
                speaker.react("learned")
        if view["voice_until"] and now >= view["voice_until"]:
            view.update(voice_text=None, voice_until=None, dirty=True)
        busy = assistant.state == "thinking"  # transcribing / asking the AI in the background
        if busy and not view["voice_dance"] and not any(r.active for r in routines):
            toggle_routine(dancer)
            view["voice_dance"] = True
        elif not busy and view["voice_dance"]:
            if dancer.active:  # done: ease out (a dance the user started is left alone)
                toggle_routine(dancer)
            view["voice_dance"] = False

        # System monitor: a cheap sample every 2s; repaint only when what it shows changed.
        if monitor.due(now):
            monitor.sample(now, detail=view["mon_open"])
            mon = monitor.view(view["mon_open"])
            key = repr(mon)
            if key != view["mon_key"]:
                view["mon_key"] = key
                view["mon_dirty"] = True
            shape = (mon["open"], len(mon["rows"]), bool(mon.get("top"))) if mon else None
            if shape != view["mon_shape"]:  # click areas moved: the main layer must know
                view["mon_shape"] = shape
                view["dirty"] = True
            view["next_alert_check"] = 0.0
        # Reminders and alarms: announce new ones right away, then nag until handled.
        if now >= view["next_alert_check"]:
            view["next_alert_check"] = now + 10
            waiting = alerts()
            ids = {a["id"] for a in waiting}
            if ids - view["alert_ids"]:
                view["next_nag"] = now + 1.0  # a beat after it appears
                after_paint.append(lambda: overlay.rect_of("alert") and effects.land(overlay.rect_of("alert")))
            if not ids:
                view["next_nag"] = None
            if ids != view["alert_ids"]:
                view["dirty"] = True
            view["alert_ids"] = ids
            view["due_count"] = len(events.due(datetime.date.today()))
        if view["next_nag"] and now >= view["next_nag"]:
            nag()
            view["next_nag"] = now + ALERT_REPEAT

        # Whole-body routines (dance, poses, walk, greet). The raised hand steps aside for them.
        busy = max(r.env for r in routines)
        if view["hand"] > 0.001:
            model.SetParamById(RAISE_HAND_PARAM, 1.0, view["hand"] * (1.0 - busy))
        shown = (dancer.active, poser.label(), walker.active, greeter.active)
        mw, mh = view["size"]
        box = view["body_box"]  # stroll room: the free width beside her, in offset units
        room = max(0.0, (mw - (box[1] - box[0])) / 2 - 8) / (max(mw, mh) / 2) if box else 0.0
        dance, pose, walk, greet = dancer.update(dt), poser.update(dt), walker.update(dt, room), greeter.update(dt)
        shift_x = shift_y = 0.0
        for params in (dance and dance[0], pose, walk and walk[0], greet):
            for param, (value, weight) in (params or {}).items():
                model.SetParamById(param, value, weight)
        if dance:
            shift_y += dance[1]
        if walk:
            shift_x, shift_y = shift_x + walk[1][0], shift_y + walk[1][1]
        moving = any(r.env > 0.0 for r in routines)
        if moving or view["was_moving"]:  # hop/stroll on top of her fitted spot, which stays saved
            model.SetOffset(view["offset"][0] + shift_x, view["offset"][1] + shift_y)
        if view["was_moving"] and not moving:  # back at rest: measure her real outline again
            refresh_silhouette(0.1)
        view["was_moving"] = moving
        if (dancer.active, poser.label(), walker.active, greeter.active) != shown:
            view["dirty"] = True  # button states / pose label changed
            view["region_dirty"] = True
        # Simulated talking: drive the mouth, plus a gentle head sway while she speaks.
        talk_shown = talker.seconds_left(now)
        speech = talker.update(now, dt)
        if speech:
            mouth, sway = speech
            model.SetParamById("ParamMouthOpenY", mouth)
            model.AddParamById("ParamAngleZ", 3.0 * sway * math.sin(talker.phase * 4.0))
        if talker.seconds_left(now) != talk_shown:  # countdown tick, or she just stopped
            view["dirty"] = True
        voice_mouth = speaker.mouth(time.monotonic())
        if voice_mouth is not None:  # speaking: lip-sync to the audio, with the Talk head sway
            model.SetParamById("ParamMouthOpenY", voice_mouth)
            model.AddParamById("ParamAngleZ", 3.0 * min(1.0, voice_mouth * 2) * math.sin(now * 4.0))
            model.AddParamById("ParamAngleY", 2.0 * voice_mouth)  # tiny nod on louder syllables

        mw, mh = view["size"]
        live2d.clearBuffer(0.0, 0.0, 0.0, 0.0)
        GL.glViewport(view["left"], 0, mw, mh)  # her area is the bottom-right block
        model.Draw()

        # Measurements from her pixels, before the UI is drawn on top.
        still = not view["drag"] and not any(r.env for r in routines)  # moving poses would mislead both
        fit_now = view["fit_due"] and now >= view["fit_due"] and still
        outline_now = view["silhouette_due"] and now >= view["silhouette_due"] and still
        if fit_now or outline_now:
            alpha = read_alpha(view["left"], mw, mh)
            if fit_now:
                scale, offset, clipped = fit_transform(alpha, view["scale"], view["offset"])
                set_transform(scale, offset)
                view["fit_passes"] += 1
                more = view["fit_passes"] < 2 or (clipped and view["fit_passes"] < 6)
                view["fit_due"] = now + 0.05 if more else None
                if not more:
                    refresh_silhouette(0.05)
                    remember_layout()
            else:
                view["silhouette"] = silhouette_rects(alpha, view["left"])
                cols = np.flatnonzero(alpha.any(axis=0))
                view["body_box"] = (int(cols[0]), int(cols[-1]) + 1) if cols.size else None
                view["silhouette_due"] = None
                rows = np.flatnonzero(alpha.any(axis=1))
                head_y = NOTES_H + int(rows[0]) if rows.size else None
                if head_y != overlay.head_y:  # buttons and the list follow her head
                    overlay.head_y = head_y
                    view["dirty"] = True
                view["region_dirty"] = True

        # Effects that follow what she is doing, and buttons springing back from a press.
        if view["flash_until"] and now >= view["flash_until"]:
            view.update(flash_until=None, dirty=True)
            overlay.flash = None
        for key, p in list(presses.items()):
            squash = p.step(dt)
            if squash:
                overlay.squash[key] = squash
            else:
                del presses[key]
                overlay.squash.pop(key, None)
            view["dirty"] = True
        hx, hy = head()
        if poser.label() != view["pose_seen"]:
            view["pose_seen"] = poser.label()
            if poser.label():
                effects.flash(hx + 60, hy + 40)
        if dancer.active and now >= view["next_rumble"]:
            if view["next_rumble"]:
                effects.rumble(hx + random.choice((-1, 1)) * 80, hy + 60)
            view["next_rumble"] = now + 4.5
        elif not dancer.active:
            view["next_rumble"] = 0.0
        if walk:
            x_now = hx + shift_x * max(mw, mh) / 2
            if walker.active and now >= view["next_step"]:
                view["next_step"] = now + 1.0 / Walker.STEPS_PER_SEC
                effects.step(x_now, win.height - 20, 1 if x_now >= view["walk_x"] else -1)
            view["walk_x"] = x_now
        if assistant.state == "listening" and now >= view["next_pulse"]:
            view["next_pulse"] = now + 0.9
            mic = overlay.rect_of("mic")
            if mic:
                effects.pulse((mic[0] + mic[2]) / 2, (mic[1] + mic[3]) / 2, 18)

        if view["dirty"] or view["mon_dirty"]:  # hover/size changes affect the pill too
            mon = monitor.view(view["mon_open"])
            if mon:
                data, (mx, my, mw_, mh_) = overlay.render_monitor(mon)
                if (mw_, mh_) != (monitor_tex.w, monitor_tex.h):
                    monitor_tex.resize(mw_, mh_)
                monitor_tex.upload(data)
                view["mon_pos"] = (mx, my)
            view["mon_dirty"] = False
        if view["dirty"]:
            cal = {"open": view["cal_open"], "month": view["cal_month"], "selected": view["cal_selected"],
                   "draft": view["cal_draft"], "editing": view["cal_editing"], "today": datetime.date.today(),
                   "events": events, "due_count": view.get("due_count", 0), "yearly": view["cal_yearly"]}
            overlay_tex.upload(overlay.render(pendings, view["open"], view["draft"], talker.seconds_left(now),
                                              active, view["moves_open"], dancer.active, poser.label(),
                                              {"walk": walker.active, "greet": greeter.active},
                                              cal=cal, alerts=alerts(), monitor=monitor.view(view["mon_open"]),
                                              voice={"state": assistant.state, "text": view["voice_text"],
                                                     "error": view["voice_error"], "command": view["voice_command"]}))
            view["dirty"] = False
            view["region_dirty"] = True  # card size or handles may have changed
            banner = overlay.rect_of("voice_banner")
            if banner and not view["banner_shown"]:
                effects.land(banner, word=None)
            view["banner_shown"] = bool(banner)
            for place in after_paint:
                place()
            after_paint.clear()
        if view["mon_shape"]:  # under the main layer, so open cards cover the monitor panel
            monitor_tex.draw(*view["mon_pos"], window_h=win.height)
        overlay_tex.draw()
        effects.bounds = (win.width, win.height)
        effects.update(dt)
        drawn = effects.render()
        if drawn:  # on top of everything; clicks still go through (not in the input region)
            data, (fx_x, fx_y, fx_w, fx_h) = drawn
            if (fx_w, fx_h) != (fx_tex.w, fx_tex.h):
                fx_tex.resize(fx_w, fx_h)
            fx_tex.upload(data, GL.GL_BGRA)
            fx_tex.draw(fx_x, fx_y, window_h=win.height)

        if view["region_dirty"] and not view["drag"]:
            ui = [(x0, y0, x1 - x0, y1 - y0) for kind, _, (x0, y0, x1, y1) in overlay.regions if kind != "item"]
            # While dancing her outline keeps moving, so her whole area takes clicks.
            dancing = any(r.env for r in routines)
            body = (not dancing and view["silhouette"]) or [(view["left"], NOTES_H, mw, mh)]
            win.set_input_region(body + ui)
            view["region_dirty"] = False

        if snapshot_at and now >= snapshot_at:
            write_snapshot(args.snapshot, win.width, win.height)
            break
        win.swap()

    remember_layout()

    model = None
    live2d.dispose()
    win.destroy()


def write_snapshot(path, w, h):
    from PIL import Image

    GL.glReadBuffer(GL.GL_BACK)
    data = GL.glReadPixels(0, 0, w, h, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
    img = np.frombuffer(data, np.uint8).reshape(h, w, 4)[::-1].astype(np.float32)
    alpha = img[..., 3:4]
    img[..., :3] = np.where(alpha > 0, img[..., :3] * 255.0 / np.maximum(alpha, 1), 0)  # un-premultiply
    Image.fromarray(img.clip(0, 255).astype(np.uint8), "RGBA").save(path)
    print(f"snapshot {path} {w}x{h}")


if __name__ == "__main__":
    main()
