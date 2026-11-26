"""Dance: a looping dance on a beat."""

import math


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
