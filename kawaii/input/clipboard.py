"""The Wayland clipboard through wl-clipboard (wl-copy / wl-paste)."""

from kawaii.features import decode


class Clipboard:
    @property
    def available(self):
        return decode.has_clipboard()

    def get(self):
        return decode.clipboard_get()

    def set(self, text):
        return decode.clipboard_set(text)
