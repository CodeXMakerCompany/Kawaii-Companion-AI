"""Editing the one-line text fields on the cards."""


def printable(text):
    """Ctrl+letters arrive as control characters: keep only what can be typed into a field."""
    return "".join(c for c in text if c.isprintable())


def erase(text, word=False):
    """Backspace; with Ctrl, the last word."""
    return text.rstrip().rpartition(" ")[0] if word else text[:-1]
