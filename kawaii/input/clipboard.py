"""The Wayland clipboard through wl-clipboard (wl-copy / wl-paste)."""

import subprocess

from kawaii.features import decode


class Clipboard:
    @property
    def available(self):
        return decode.has_clipboard()

    def get(self):
        return decode.clipboard_get()

    def set(self, text):
        return decode.clipboard_set(text)

    def clear(self):
        """Empty it (after a Vault key was copied)."""
        try:
            subprocess.run(["wl-copy", "--clear"], timeout=3)
        except (OSError, subprocess.SubprocessError):
            pass
