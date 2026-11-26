"""How she reacts to the Kiro / Claude agents: while one waits on you she goes 'huh?' at
its icon (whenever she is free); otherwise, while any works, she thinks it over looking at
its icon; when the last one is done she gets it. Stopping either by hand sticks until the
agents move on."""


class AgentReactions:
    def __init__(self, body):
        self.body = body
        self.working = False  # an agent works in Kiro or Claude
        self.waiting = False  # an agent waits on you
        self.thinking = False  # she is thinking because of them
        self.think_dismissed = False  # you stopped her thinking while they work
        self.puzzled = False  # she is going 'huh?' because of them
        self.huh_dismissed = False  # you stopped the 'huh?' while they wait
        self.huh_beats = 0  # double takes already given their effects
        self.ponder_at = 0.0  # next thought bubble while thinking

    def update(self, now, working, waiting):
        """working / waiting: the icon sides (1 right, -1 left) of the agents in that state.
        Returns effects to play: "puzzled" (a new double take), "aha" (they are all done)."""
        body, thinker, huh = self.body, self.body.thinker, self.body.huh
        events = []
        self.working, self.waiting = bool(working), bool(waiting)
        if waiting:
            if huh.active and huh.side not in waiting:
                huh.side = waiting[0]
            free = body.free_except(thinker) and not self.huh_dismissed
            if free and not huh.active and (thinker.active or not body.busy):
                if thinker.active:
                    thinker.stop(aha=False)  # not done: it needs you
                huh.side = waiting[0]
                body.toggle(huh)
                self.puzzled = True
        elif self.puzzled or self.huh_dismissed:
            if self.puzzled and huh.active:
                body.toggle(huh)  # answered: she relaxes (and thinks again if it works on)
            self.puzzled = self.huh_dismissed = False
        if huh.beats != self.huh_beats:  # a double take: its little burst as the '?' pops up
            self.huh_beats = huh.beats
            events.append("puzzled")
        if not waiting:  # thinking waits while something needs you
            if working:
                if thinker.side not in working:  # the one she was looking at is done
                    thinker.side = working[0]
                if not self.think_dismissed and not body.busy:
                    thinker.side = working[0]
                    body.toggle(thinker)
                    self.thinking, self.ponder_at = True, now + 0.7
            elif self.thinking or self.think_dismissed:
                if self.thinking and thinker.active:
                    body.toggle(thinker)
                    events.append("aha")
                self.thinking = self.think_dismissed = False
        return events

    def user_toggled_think(self, now):
        """Think was clicked (after the body toggled it)."""
        if self.body.thinker.active:
            self.ponder_at = now + 0.7  # once the hand is up
        else:
            self.think_dismissed = self.working  # not again until they are done

    def user_toggled_huh(self):
        if self.body.huh.active:
            self.body.huh.side = 1  # your own 'huh?': at the empty space beside her
        else:
            self.huh_dismissed = self.waiting

    def ponder(self, now, card_open):
        """Time for a thought bubble? None, or whether it is a cloud (False: a trail leading
        to the agent's icon she is looking at). Never over a card: card_open() says if one is
        open (asked only when a bubble is due, as it reads the painted layout)."""
        if not self.body.thinker.active or now < self.ponder_at or card_open():
            return None
        self.ponder_at = now + 6.5
        return not (self.thinking and self.working)
