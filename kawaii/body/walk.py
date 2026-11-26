"""Walk: she strolls side to side across her area."""

import math


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
