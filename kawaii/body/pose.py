"""Pose: five photo poses in a row."""


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
