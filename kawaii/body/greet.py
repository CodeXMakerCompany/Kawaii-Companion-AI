"""Greet: a one-shot bow and wave."""

import math


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
