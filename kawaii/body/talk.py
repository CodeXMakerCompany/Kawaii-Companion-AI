"""Fake speech for her mouth, for when she has no voice to lip-sync to."""

import random


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
