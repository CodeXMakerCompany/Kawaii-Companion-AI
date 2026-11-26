"""The cards that open above her head, one at a time, and what they may ask of the screen."""

import time

from kawaii.input.keys import BTN_LEFT
from kawaii.render.fx import Press


class Screen:
    """The painted UI as cards and controls see it: ask for a repaint, play an effect, find
    where something is drawn, or place an effect once the next repaint has laid things out."""

    def __init__(self, overlay, effects):
        self.overlay, self.fx = overlay, effects
        self.dirty = True  # the overlay needs repainting
        self.region_dirty = True  # the input region needs resending
        self.after_paint = []  # effects placed by the next repaint's layout (the caret, a new bubble)
        self.presses = {}  # hit -> Press, for buttons springing back from a click
        self.mouse = (-1.0, -1.0)

    def redraw(self):
        self.dirty = True

    def rect(self, kind, name=None):
        return self.overlay.rect_of(kind, name)

    def under_mouse(self):
        return self.overlay.hit(*self.mouse)

    def press(self, hit):
        self.presses[hit] = Press()

    def after(self, place):
        self.after_paint.append(place)

    def caret_dust(self):
        """A puff where the caret moved to, once the typed text is painted."""
        self.after(lambda: self.overlay.caret and self.fx.dust(*self.overlay.caret))


def clamp_skip(skip, steps, rows):
    """Wheel down (negative steps) scrolls further down the list."""
    return max(0, min(skip - steps, rows - 1))


def clock(timestamp):
    """HH:MM of a time.time() stamp, for "checked at" lines; None before the first check."""
    return time.strftime("%H:%M", time.localtime(timestamp)) if timestamp else None


def middle(rect):
    return (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2


class Card:
    """One card. Subclasses set what opens them and which hit kinds they own, and override
    the hooks they need; the Deck routes input to them."""

    name = ""
    opener = None  # the (kind, name) hit that toggles this card
    open_fx = "pick"  # "pop": pops open and poofs shut; "pick": a tap when opening
    hits = ()  # hit kinds this card's clicks go to
    scroll_hits = ()  # hit kinds over which the wheel scrolls this card

    def __init__(self, screen):
        self.screen = screen
        self.fx = screen.fx
        self.is_open = False
        self.deck = None

    def close(self):
        self.deck.show(self.name, False)

    def opened(self):
        """Just opened (every other card is closed by now)."""

    def closed(self):
        """Just closed."""

    def click(self, hit, button, rect):
        """A click on one of this card's hit kinds."""

    def key(self, key, ctrl):
        """A key while open; True when used (the others fall through to her hotkeys)."""
        return False

    def text(self, text):
        """Typed text while open."""

    def scroll(self, steps):
        """The wheel over this card while open."""

    def tick(self, now):
        """Every frame, open or not: background work coming back."""

    def payload(self):
        """What the overlay needs to draw this card."""
        return {"open": self.is_open}


class Deck:
    def __init__(self, *cards):
        self.cards = {c.name: c for c in cards}
        for c in cards:
            c.deck = self

    def __getitem__(self, name):
        return self.cards[name]

    @property
    def current(self):
        return next((c for c in self.cards.values() if c.is_open), None)

    def show(self, name, on=True):
        card = self.cards[name]
        if on:
            for other in self.cards.values():
                if other is not card and other.is_open:
                    self.show(other.name, False)
        if card.is_open == on:
            return
        card.is_open = on
        card.opened() if on else card.closed()
        card.screen.redraw()

    def toggle(self, name):
        self.show(name, not self.cards[name].is_open)
        return self.cards[name].is_open

    def click(self, hit, button, rect):
        """Opens/closes the card whose opener was hit, or hands the click to its card."""
        if hit is None:
            return False
        for card in self.cards.values():
            if hit == card.opener:
                if button != BTN_LEFT:
                    return False
                if self.toggle(card.name):
                    card.fx.pop(rect) if card.open_fx == "pop" else card.fx.pick(rect)
                elif card.open_fx == "pop":
                    card.fx.poof(rect[2] - 16, (rect[1] + rect[3]) / 2)
                return True
            if hit[0] in card.hits:
                card.click(hit, button, rect)
                return True
        return False

    def key(self, key, ctrl):
        card = self.current
        return bool(card and card.key(key, ctrl))

    def text(self, text):
        if self.current:
            self.current.text(text)

    def scroll(self, steps, hit):
        card = self.current
        if card and hit and hit[0] in card.scroll_hits:
            card.scroll(steps)
            return True
        return False

    def tick(self, now):
        for card in self.cards.values():
            card.tick(now)
