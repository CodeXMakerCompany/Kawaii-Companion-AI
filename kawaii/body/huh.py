"""Huh?: double takes at something waiting on you."""

import math
import random


class Huh:
    """'Huh?': something is waiting on you. She does a double take at it (eyes first, then
    the head, to the side it is on), turns back to you with her head cocked, brows up, a
    little 'huh?' and the model's '?' popping up by her head. Between double takes she
    waits looking at you, swaying a little and glancing over at it now and then; the double
    takes come less often the longer it waits, so a long wait doesn't turn into a loop."""

    QUESTION = "Param61"  # 疑问: a '?' by her head (it also blanks her eyes, so only in the beats)
    IN, OUT = 0.35, 0.5
    BEAT = 2.4  # seconds one double take lasts

    def __init__(self):
        self.t = None  # seconds into the wait, None when not waiting
        self.env = 0.0
        self.side = 1  # where the waiting thing is: 1 screen-right, -1 screen-left
        self.clock, self.phase = 0.0, 0.0
        self.beat_at, self.next_beat, self.gap = 0.0, 0.0, 7.0
        self.beats = 0  # double takes so far (the viewer adds effects to each)
        self.mark = 0.0  # the '?' drawing, switched in fast
        self.eye, self.look = [0.0, 0.0], [0.0, 0.0]
        self.peek_at, self.next_peek = None, 0.0  # a glance at it between double takes

    @property
    def active(self):
        return self.t is not None

    def toggle(self):
        if self.active:
            self.stop()
        else:
            self.t, self.beat_at, self.gap = 0.0, 0.0, 7.0
            self.next_beat, self.next_peek = self.BEAT + self.gap, self.BEAT + 2.0
            self.beats += 1  # the first double take starts right away
            self.phase = random.uniform(0, 100)

    def stop(self):
        self.t = None

    def update(self, dt):
        """Advance; returns {param: (value, weight)} or None when she isn't waiting."""
        self.clock += dt
        b = None  # seconds into the current double take
        if self.active:
            self.t += dt
            if self.t >= self.next_beat:
                self.beat_at, self.beats = self.t, self.beats + 1
                self.next_beat = self.t + self.BEAT + self.gap
                self.gap = min(30.0, self.gap * 1.35)  # less and less often
            b = self.t - self.beat_at if self.t - self.beat_at < self.BEAT else None
            if b is None and self.t >= self.next_peek:
                self.peek_at, self.next_peek = self.t, self.t + random.uniform(2.5, 4.5)
            peeking = self.peek_at is not None and self.t - self.peek_at < 0.8 and b is None
            if b is not None and b < 0.45:  # the double take: a look at it...
                target = (0.8 * self.side, 0.3)
            elif peeking:
                target = (0.65 * self.side, 0.2)
            else:  # ...then at you
                target = (0.08 * math.sin(self.clock * 0.7 + self.phase), 0.05)
            want_mark = 1.0 if b is not None and 0.5 <= b < 2.0 else 0.0
        else:
            target, want_mark = (0.0, 0.0), 0.0
        self.env = min(1.0, self.env + dt / self.IN) if self.active else max(0.0, self.env - dt / self.OUT)
        self.mark += max(-dt / 0.12, min(dt / 0.12, want_mark - self.mark))
        if self.env == 0.0:
            return None

        k_eye, k_head = 1 - math.exp(-dt * 30), 1 - math.exp(-dt * 3.0)
        for i in (0, 1):
            self.eye[i] += (target[i] - self.eye[i]) * k_eye
            self.look[i] += (self.eye[i] - self.look[i]) * k_head

        def ramp(a, c):  # 0 before a, 1 after c, smooth in between (over the double take)
            if b is None:
                return 0.0
            k = min(1.0, max(0.0, (b - a) / (c - a)))
            return k * k * (3 - 2 * k)

        cock = 0.45 + 0.55 * ramp(0.4, 0.75) * (1 - ramp(1.9, self.BEAT))  # head cocked, more in a beat
        back = ramp(0.45, 0.6) * (1 - ramp(0.6, 0.95))  # a little jerk back on 'huh?'
        huh = ramp(0.5, 0.65) * (1 - ramp(0.75, 1.0))  # the syllable
        sway = math.sin(0.8 * self.clock + self.phase)
        lx, ly = self.look
        e = self.env * self.env * (3 - 2 * self.env)
        return {
            "ParamAngleX": (-16 * lx + sway, e),
            "ParamAngleY": (6 * ly + 4 * back, e),
            "ParamAngleZ": (self.side * (4 + 9 * cock), e),
            "ParamEyeBallX": (self.eye[0], e),
            "ParamEyeBallY": (self.eye[1], e),
            "ParamBodyAngleX": (-3 * lx, e),
            "ParamBodyAngleY": (2 * back, e),
            "ParamBodyAngleZ": (self.side * 2.5 * cock, e),
            "ParamBrowLY": (0.25 + 0.55 * cock, e),  # both up, one more
            "ParamBrowRY": (0.1 + 0.4 * cock, e),
            "ParamBrowLAngle": (0.3 * cock, e),
            "Param13": (0.35 * cock * self.side, e),  # a puzzled, crooked mouth
            "ParamMouthForm": (-0.35, e),
            "ParamMouthOpenY": (0.4 * huh, e),
            self.QUESTION: (self.mark, 1.0 if self.mark > 0 else e),
        }
