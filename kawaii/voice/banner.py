"""The voice banner: what the voice assistant heard, ran, or wants you to confirm, and her
spoken reactions to it. She dances while it transcribes or asks the AI."""

BANNER_SECONDS = 6
ERROR_REACTIONS = ("not_open", "open_failed", "ai_failed", "refused", "not_heard", "no_command", "ai_down")


class VoiceBanner:
    def __init__(self, screen, assistant, speaker, body, mover, app_output):
        self.screen, self.assistant, self.speaker, self.body = screen, assistant, speaker, body
        self.mover, self.app_output = mover, app_output
        self.text = None  # banner text
        self.error = False
        self.command = None  # AI suggestion (or a "confirm" command like power off) waiting for Run/Cancel
        self.ai = False  # that command came from the AI (approving it teaches it)
        self.until = None  # hide the banner after this time
        self.heard = ""
        self.toggle_requested = False  # set by SIGUSR1 (the global shortcut script)
        self.dancing = False  # she dances because a voice command is being processed
        self.shown = False  # the banner was on screen at the last repaint

    def request_toggle(self):
        """Safe from a signal handler: acted on at the next frame."""
        self.toggle_requested = True

    def _talk_if_silent(self, seconds):
        if not self.speaker.available:
            self.body.talk(seconds)  # no voice: at least move her mouth

    def tick(self, now):
        if self.toggle_requested:
            self.toggle_requested = False
            self.assistant.toggle()
        self.assistant.tick()
        for ev in self.assistant.poll():
            self.handle(ev, now)
        if self.until and now >= self.until:
            self.text = self.until = None
            self.screen.redraw()
        busy = self.assistant.state == "thinking"  # transcribing / asking the AI in the background
        if busy and not self.dancing and not self.body.busy:
            self.body.toggle(self.body.dancer)
            self.dancing = True
        elif not busy and self.dancing:
            if self.body.dancer.active:  # done: ease out (a dance the user started is left alone)
                self.body.toggle(self.body.dancer)
            self.dancing = False

    def handle(self, ev, now):
        """One event from the assistant's worker; she says it out loud when a command runs."""
        kind = ev[0]
        meta = ev[-1] if isinstance(ev[-1], dict) else {}
        self.error, self.until = False, None
        self.screen.redraw()
        if self.assistant.state != "confirm":  # a "didn't catch that" while she waits keeps Run/Cancel
            self.command = None
        if self.assistant.state == "listening":
            self.speaker.stop()  # never record her own voice
        if kind == "status":
            self.text = ev[1]
            if meta.get("kind") == "cancelled":
                self.speaker.react("cancelled")
        elif kind == "heard":
            self.heard = ev[1]
            self.text = f"“{ev[1]}”"
        elif kind == "run":
            self.text = f"“{self.heard}”: {ev[2]}  ($ {ev[1]})"
            self.until = now + BANNER_SECONDS
            if meta.get("kind") == "open":  # its window goes to your monitor too
                self.mover.expect(self.app_output(), seconds=15, lookback=4)  # it may have opened already
            if meta.get("kind") in ("open", "close"):
                self.speaker.react(meta["kind"], app=meta.get("app"))
            else:  # learned/AI commands: their "say" may be in another language than her voice
                self.speaker.react(meta.get("react") or "ran")  # e.g. "poweroff": she says goodbye
            self._talk_if_silent(2)
        elif kind == "confirm":
            self.command, self.ai = ev[1], meta.get("kind") == "ai"
            if self.ai:
                self.text = f"AI suggests for “{self.heard}”: {ev[2]}".rstrip(": ")
                self.speaker.react("confirm_ai")  # "I found this command. Wanna check it first?"
            else:  # a commands.json entry marked "confirm", like turning the PC off
                self.text = f"“{self.heard}”: {ev[2]}?"
                self.speaker.react(f"confirm_{meta['react']}" if meta.get("react") else "confirm_command")
            self._talk_if_silent(1.5)
        elif kind == "error":
            self.text, self.error, self.until = ev[1], True, now + BANNER_SECONDS
            if meta.get("kind") in ERROR_REACTIONS:
                self.speaker.react(meta["kind"], app=meta.get("app"))
        elif kind == "learned":  # an approved AI command worked and is now a regular command
            self.text, self.until = f"Learned “{ev[1]}”: saved to commands.json", now + BANNER_SECONDS
            self.speaker.react("learned")

    def payload(self):
        return {"state": self.assistant.state, "text": self.text, "error": self.error, "command": self.command,
                "ai": self.ai}
