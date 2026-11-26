"""Think: finger on her chin, mulling it over, then 'got it'."""

import math
import random


class Thinker:
    """A thinking pose: finger on her chin (the 点点 drawing), head leaning into the hand,
    eyes wandering up and away while she mulls it over, then a small 'got it' when it ends.

    Nothing loops, so it reads as thinking rather than an animation: the eyes jump to a new
    spot at random moments (now and then down at nothing) and the head follows a beat
    later, the sway is two slow unrelated sines, the mouth purses on and off. Ending it
    lifts her brows, drops the hand, and she smiles with a little nod."""

    HAND = "Param79"  # 点点: index finger on her chin
    IN, OUT, AHA = 0.8, 0.6, 1.0  # seconds: settle in, relax, the 'got it'
    TILT = 1  # head and body lean toward the hand (screen-left)

    def __init__(self):
        self.t = None  # seconds into the thought, None when not thinking
        self.aha = None  # seconds into the 'got it', after stopping
        self.env = 0.0  # overall weight, eases in/out
        self.hand = 0.0  # the hand drawing: switched in fast, a slow cross-fade looks ghostly
        self.clock = 0.0
        self.phase = 0.0
        self.eye = [0.0, 0.0]  # gaze: snaps to a new spot (a saccade)
        self.look = [0.0, 0.0]  # where the head points: follows the gaze slowly
        self.target = (0.0, 0.0)
        self.next_glance = 0.0
        self.purse, self.purse_to = 0.0, 0.0
        self.side = 1  # which way she looks: 1 screen-right, -1 screen-left (set before starting)

    @property
    def active(self):
        return self.t is not None

    def toggle(self):
        if self.active:
            self.stop()
        else:
            self.t, self.aha, self.next_glance = 0.0, None, 0.3
            self.phase = random.uniform(0, 100)  # the sway starts somewhere new each time

    def stop(self, aha=True):
        """aha=False: just relax (it isn't over, something else needs her)."""
        if self.active:
            self.t, self.aha = None, 0.0 if aha else None

    @staticmethod
    def _glance():
        """A spot up and to her looking side; now and then down, considering."""
        if random.random() < 0.22:
            return random.uniform(-0.1, 0.35), random.uniform(-0.45, -0.2)
        return random.uniform(0.35, 0.85), random.uniform(0.35, 0.8)

    def update(self, dt):
        """Advance; returns {param: (value, weight)} or None when she isn't thinking."""
        self.clock += dt
        if self.active:
            self.t += dt
            if self.t >= self.next_glance:
                gx, gy = self._glance()
                self.target = (gx * self.side, gy)
                self.next_glance = self.t + random.uniform(0.9, 2.6)
            if random.random() < dt / 2.2:  # a thoughtful purse of the lips, on and off
                self.purse_to = random.uniform(0.15, 0.6) if random.random() < 0.6 else 0.0
        else:
            self.target, self.purse_to = (0.0, 0.1), 0.0  # back to looking ahead
        if self.aha is not None:
            self.aha += dt
            if self.aha >= self.AHA:
                self.aha = None
        settling = self.active or self.aha is not None
        self.env = min(1.0, self.env + dt / self.IN) if settling else max(0.0, self.env - dt / self.OUT)
        want_hand = 1.0 if self.active and self.t > 0.3 else 0.0
        self.hand += max(-dt / 0.16, min(dt / 0.16, want_hand - self.hand))
        if self.env == 0.0:
            return None

        k_eye, k_head = 1 - math.exp(-dt * 28), 1 - math.exp(-dt * 2.2)
        for i in (0, 1):
            self.eye[i] += (self.target[i] - self.eye[i]) * k_eye
            self.look[i] += (self.eye[i] - self.look[i]) * k_head
        self.purse += (self.purse_to - self.purse) * (1 - math.exp(-dt * 4))
        c, ph = self.clock, self.phase
        sway = 0.6 * math.sin(0.7 * c + ph) + 0.4 * math.sin(1.13 * c + 2 * ph)
        drift = math.sin(0.53 * c + 3 * ph)

        def bump(a, b):  # 0 -> 1 -> 0 over the 'got it' seconds a..b
            k = (self.aha - a) / (b - a) if self.aha is not None else -1
            return math.sin(math.pi * k) if 0 <= k <= 1 else 0.0

        smile = min(1.0, self.aha / 0.35) if self.aha is not None else 0.0
        brows_up, nod, oh = bump(0.0, 0.9), bump(0.2, 0.65), bump(0.05, 0.4)
        lx, ly = self.look
        e = self.env * self.env * (3 - 2 * self.env)  # smoothstep
        lean = self.TILT * (1 - smile * 0.6)
        params = {
            "ParamAngleX": (-14 * lx + 1.5 * sway, e),
            "ParamAngleY": (9 * ly + drift - 7 * nod, e),
            "ParamAngleZ": (lean * (7 + 1.5 * sway), e),
            "ParamEyeBallX": (self.eye[0], e),
            "ParamEyeBallY": (self.eye[1], e),
            "ParamBodyAngleX": (-3 * lx, e),
            "ParamBodyAngleY": (-1.5, e),
            "ParamBodyAngleZ": (lean * 2.5, e),
            "ParamBrowLY": (0.35 * (1 - smile) + 0.7 * brows_up, e),  # one brow up, the other knit
            "ParamBrowRY": (-0.15 * (1 - smile) + 0.7 * brows_up, e),
            "ParamBrowRAngle": (-0.35 * (1 - smile), e),
            "ParamBrowRForm": (-0.4 * (1 - smile), e),
            "Param13": (self.purse * (1 - smile), e),
            "ParamMouthForm": (-0.25 * (1 - smile) + 0.9 * smile, e),
            "ParamMouthOpenY": (0.3 * oh, e),
            "ParamEyeLSmile": (0.5 * smile, e),
            "ParamEyeRSmile": (0.5 * smile, e),
            "ParamCheek": (0.25 * smile, e),
            self.HAND: (self.hand, 1.0 if self.hand > 0 else e),
        }
        return params
