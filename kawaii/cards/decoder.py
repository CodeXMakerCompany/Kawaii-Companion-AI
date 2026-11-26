"""Decode: paste or type a JWT, timestamp, JSON, base64, URL, stack trace...: Decode shows
it readable, Copy copies it, Explain? sends a stack trace to OpenRouter (she thinks it over
with you). Enter decodes, Ctrl+V pastes, Ctrl+C copies, Esc closes."""

from kawaii.cards.base import Card, clamp_skip
from kawaii.features import decode as decoders
from kawaii.input.keys import BTN_LEFT, ENTER, KEY_BACKSPACE, KEY_C, KEY_ESC, KEY_V
from kawaii.input.textfield import erase, printable


class DecoderCard(Card):
    name = "decoder"
    opener = ("action", "decode")
    hits = ("dec_paste", "dec_run", "dec_clear", "dec_copy", "dec_explain")
    scroll_hits = ("dec_card", "dec_input")

    def __init__(self, screen, clipboard, explainer, body, head, decode=decoders.decode):
        super().__init__(screen)
        self.clipboard, self.explainer, self.body, self.head, self.decode = clipboard, explainer, body, head, decode
        self.draft = ""  # what is being decoded
        self.result = None  # decode.Result
        self.status = ""  # a short note: Copied!, Asking..., why it failed
        self.explanation = None  # OpenRouter's explanation of the stack trace
        self.skip = 0  # result rows scrolled past
        self.thinking = False  # she is thinking while the explanation comes

    def run(self, rect=None):
        """Decode the draft: the result shows in the card."""
        self.result = self.decode(self.draft)
        self.explanation, self.skip = None, 0
        self.status = "" if self.result or not self.draft.strip() else "Nothing to decode"
        if self.result and rect:
            self.fx.done(rect)
        self.screen.redraw()

    def paste(self, rect=None):
        text = self.clipboard.get() if self.clipboard.available else None
        if text is None:
            self.status = ("Install wl-clipboard to paste" if not self.clipboard.available
                           else "The clipboard has no text")
            self.screen.redraw()
            return
        self.draft = text
        self.run(rect)  # pasting is asking: show it right away

    def copy(self, rect=None):
        text = self.explanation or (self.result.copy if self.result else None)
        if not text:
            return
        if self.clipboard.set(text):
            self.status = "Copied!"
            if rect:
                self.fx.done(rect)
        else:
            self.status = "Install wl-clipboard to copy"
        self.screen.redraw()

    def explain(self):
        """The only thing here that leaves the machine."""
        if self.explainer.busy:
            return
        self.explainer.start(self.draft)
        self.status = "Asking OpenRouter…"
        self.screen.redraw()
        if not self.body.busy:
            self.body.toggle(self.body.thinker)  # she thinks it over with you
            self.thinking = True

    def click(self, hit, button, rect):
        if button != BTN_LEFT:
            return
        self.screen.press(hit)
        kind = hit[0]
        if kind == "dec_paste":
            self.paste(rect)
        elif kind == "dec_run":
            self.run(rect)
        elif kind == "dec_clear":
            self.draft, self.result, self.explanation, self.status = "", None, None, ""
            self.screen.redraw()
        elif kind == "dec_copy":
            self.copy(rect)
        else:
            self.explain()

    def key(self, key, ctrl):
        if key == KEY_ESC:
            self.close()
        elif key in ENTER:
            self.run(self.screen.rect("dec_run"))
        elif key == KEY_V and ctrl:
            self.paste(self.screen.rect("dec_run"))
        elif key == KEY_C and ctrl:
            self.copy(self.screen.rect("dec_copy"))
        elif key == KEY_BACKSPACE and self.draft:
            self.draft = erase(self.draft, word=ctrl)
            self.screen.redraw()
        return True

    def text(self, text):
        typed = printable(text)
        if typed:
            self.draft += typed
            self.screen.redraw()

    def scroll(self, steps):
        self.skip = clamp_skip(self.skip, steps, self.screen.overlay.dec_rows)
        self.screen.redraw()

    def tick(self, now):
        """An explanation of a stack trace came back from OpenRouter."""
        answer = self.explainer.poll()
        if not answer:
            return
        text, error = answer
        self.explanation, self.status = text, "" if text else f"No explanation: {error}"
        self.screen.redraw()
        thinker = self.body.thinker
        if self.thinking and thinker.active:
            self.body.toggle(thinker)  # she gets it
            self.fx.later(0.15, lambda: self.fx.idea(*self.head(), thinker.side))
        self.thinking = False

    def payload(self):
        return {"open": self.is_open, "draft": self.draft, "result": self.result, "status": self.status,
                "explanation": self.explanation, "skip": self.skip, "clipboard": self.clipboard.available}
