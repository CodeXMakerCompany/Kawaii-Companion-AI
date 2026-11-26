"""Everything that moves her body: one whole-body routine at a time, the raised hand
for the Pendings card, and her mouth (simulated talk, or lip-sync to her real voice)."""

import math
from dataclasses import dataclass

from kawaii.body.dance import Dancer
from kawaii.body.greet import Greeter
from kawaii.body.huh import Huh
from kawaii.body.pose import PoseShow
from kawaii.body.talk import TalkSimulator
from kawaii.body.think import Thinker
from kawaii.body.walk import Walker

# 比耶 (peace sign) pose: lifts her right hand to face height, the other arm stays down.
RAISE_HAND_PARAM = "Param77"
RAISE_HAND_SPEED = 8.0  # higher = faster blend


@dataclass
class Motion:
    """What one frame of movement means for the rest of the app."""
    shift: tuple = (0.0, 0.0)  # hop/stroll on top of her fitted offset (offset units)
    walking: bool = False  # the walk routine moved her this frame
    changed: bool = False  # a routine started/stopped or the pose changed: buttons repaint
    settled: bool = False  # she just came back to rest: her outline can be measured again
    talk_changed: bool = False  # the Talk countdown ticked or ended


class Body:
    def __init__(self, on_toggle=None):
        self.on_toggle = on_toggle  # a routine started or stopped outside the frame update: repaint the buttons
        self.talker = TalkSimulator()
        self.dancer = Dancer()
        self.poser = PoseShow()
        self.walker = Walker()
        self.greeter = Greeter()
        self.thinker = Thinker()
        self.huh = Huh()
        self.routines = (self.dancer, self.poser, self.walker, self.greeter, self.thinker, self.huh)
        self._names = {"dance": self.dancer, "pose": self.poser, "walk": self.walker, "greet": self.greeter,
                       "think": self.thinker, "huh": self.huh}
        self.hand = 0.0  # current raise-hand blend weight
        self.clock = 0.0  # seconds of animation so far (the talk timer runs on it)
        self.was_moving = False

    def by_name(self, name):
        """The routine behind a button ("dance", "pose", "walk", "greet", "think", "huh")."""
        return self._names[name]

    def toggle(self, routine):
        """Each routine drives her whole body, so starting one stops the others."""
        for other in self.routines:
            if other is not routine and other.active:
                other.toggle()  # toggling an active routine stops it
        routine.toggle()
        if self.on_toggle:
            self.on_toggle()

    @property
    def busy(self):
        return any(r.active for r in self.routines)

    @property
    def moving(self):
        """Still easing in or out counts: her outline is not where it will settle."""
        return any(r.env > 0.0 for r in self.routines)

    def free_except(self, routine):
        return not any(r.active for r in self.routines if r is not routine)

    def signature(self):
        """What the buttons show about her routines (compared across frames to repaint)."""
        return (self.dancer.active, self.poser.label(), self.walker.active, self.greeter.active,
                self.thinker.active, self.huh.active)

    def talk(self, seconds):
        self.talker.start(self.clock, seconds)

    def stop_talking(self):
        self.talker.stop()

    def talk_left(self):
        return self.talker.seconds_left(self.clock)

    def update(self, model, dt, hand_up, room, offset, voice_mouth=None):
        """Advance every routine by dt and pose the model.

        hand_up: the Pendings card is open. room: stroll room (offset units). offset: her
        fitted offset, which hops and strolls move around without changing.
        voice_mouth: her mouth opening while her real voice plays, else None."""
        talk_shown = self.talk_left()
        self.clock += dt
        motion = Motion()
        # Ease the raised hand in/out; only touch the parameter while it is in use.
        self.hand += ((1.0 if hand_up else 0.0) - self.hand) * min(1.0, dt * RAISE_HAND_SPEED)
        busy = max(r.env for r in self.routines)
        if self.hand > 0.001:
            model.SetParamById(RAISE_HAND_PARAM, 1.0, self.hand * (1.0 - busy))  # steps aside for routines

        shown = self.signature()
        dance, pose, walk = self.dancer.update(dt), self.poser.update(dt), self.walker.update(dt, room)
        greet, think, puzzled = self.greeter.update(dt), self.thinker.update(dt), self.huh.update(dt)
        for params in (dance and dance[0], pose, walk and walk[0], greet, think, puzzled):
            for param, (value, weight) in (params or {}).items():
                model.SetParamById(param, value, weight)
        shift_x = shift_y = 0.0
        if dance:
            shift_y += dance[1]
        if walk:
            shift_x, shift_y = shift_x + walk[1][0], shift_y + walk[1][1]
        motion.shift, motion.walking = (shift_x, shift_y), bool(walk)
        moving = self.moving
        if moving or self.was_moving:
            model.SetOffset(offset[0] + shift_x, offset[1] + shift_y)
        motion.settled = self.was_moving and not moving
        self.was_moving = moving
        motion.changed = self.signature() != shown

        # Simulated talking: drive the mouth, plus a gentle head sway while she speaks.
        speech = self.talker.update(self.clock, dt)
        if speech:
            mouth, sway = speech
            model.SetParamById("ParamMouthOpenY", mouth)
            model.AddParamById("ParamAngleZ", 3.0 * sway * math.sin(self.talker.phase * 4.0))
        motion.talk_changed = self.talk_left() != talk_shown
        if voice_mouth is not None:  # speaking: lip-sync to the audio, with the Talk head sway
            model.SetParamById("ParamMouthOpenY", voice_mouth)
            model.AddParamById("ParamAngleZ", 3.0 * min(1.0, voice_mouth * 2) * math.sin(self.clock * 4.0))
            model.AddParamById("ParamAngleY", 2.0 * voice_mouth)  # tiny nod on louder syllables
        return motion
