"""The Vault: API keys and temporary tokens kept at hand, each under the reason you keep it
(like Business Rules: the reason first, then its keys).

Saved as plain text, one key per line: reason<TAB>name<TAB>key<TAB>expires (unix time,
empty for keys that keep); a reason with no keys yet is a line with just its name. The
file is created readable by you only (mode 600) and you may edit it by hand. Nothing in
the app sends it anywhere: the screen only ever gets keys masked (see mask), and the AI
features (voice, Explain?) never see it.
"""

import os
import sys
import time
from pathlib import Path

TEMP_SECONDS = 24 * 3600  # a temporary key deletes itself after a day
HEADER = ("# Shark Girl's Vault: reason<TAB>name<TAB>key<TAB>expires (unix time, empty = keeps)\n"
          "# Kept on this computer only (mode 600). Nothing in the app sends it to an AI.\n")


def mask(secret):
    """What the screen shows of a key: its first and last four characters at most."""
    return f"{secret[:4]}…{secret[-4:]}" if len(secret) >= 12 else "•" * 8


def _clean(text):
    """One line, no tabs: a key or name as it can be saved."""
    return "".join(text.split()) if text else ""


class Vault:
    def __init__(self, path, now=time.time):
        self.path, self.now = Path(path), now
        self.reasons = []  # [{"name", "keys": [{"name", "secret", "expires"}]}]
        self._load()
        self.purge()

    def find(self, name):
        name = " ".join(name.split()).lower()
        return next((i for i, r in enumerate(self.reasons) if r["name"].lower() == name), None)

    def add_reason(self, name):
        """Index of the reason called `name` (added if new), or None for a blank name."""
        before = len(self.reasons)
        index = self._reason(name)
        if len(self.reasons) != before:
            self.save()
        return index

    def remove_reason(self, index):
        if 0 <= index < len(self.reasons):
            del self.reasons[index]
            self.save()

    def add_key(self, reason, name, secret, temporary=False):
        name, secret = " ".join(name.split()), _clean(secret)
        if not name or not secret or not 0 <= reason < len(self.reasons):
            return False
        expires = self.now() + TEMP_SECONDS if temporary else None
        self.reasons[reason]["keys"].append({"name": name, "secret": secret, "expires": expires})
        self.save()
        return True

    def remove_key(self, reason, index):
        keys = self.reasons[reason]["keys"] if 0 <= reason < len(self.reasons) else []
        if 0 <= index < len(keys):
            del keys[index]
            self.save()

    @property
    def count(self):
        return sum(len(r["keys"]) for r in self.reasons)

    def purge(self):
        """Drop the temporary keys whose day is over; True when any went."""
        now, gone = self.now(), False
        for r in self.reasons:
            kept = [k for k in r["keys"] if k["expires"] is None or k["expires"] > now]
            gone = gone or len(kept) != len(r["keys"])
            r["keys"] = kept
        if gone:
            self.save()
        return gone

    def _load(self):
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return
        for line in lines:
            if not line.strip() or line.startswith("#"):
                continue
            reason, name, secret, expires = (line.split("\t") + ["", "", ""])[:4]
            index = self._reason(reason)
            if index is None or not name.strip() or not secret.strip():
                continue
            try:
                when = float(expires) if expires.strip() else None
            except ValueError:
                when = None
            self.reasons[index]["keys"].append({"name": name.strip(), "secret": secret.strip(), "expires": when})

    def _reason(self, name):
        """add_reason without saving (also used while reading the file)."""
        name = " ".join(name.split())
        if not name:
            return None
        index = self.find(name)
        if index is None:
            self.reasons.append({"name": name, "keys": []})
            index = len(self.reasons) - 1
        return index

    def save(self):
        lines = [HEADER]
        for r in self.reasons:
            if not r["keys"]:
                lines.append(f"{r['name']}\n")
            for k in r["keys"]:
                expires = "" if k["expires"] is None else str(int(k["expires"]))
                lines.append(f"{r['name']}\t{k['name']}\t{k['secret']}\t{expires}\n")
        tmp = self.path.with_name(self.path.name + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.writelines(lines)
            os.chmod(tmp, 0o600)
            os.replace(tmp, self.path)
        except OSError as e:
            print(f"vault: cannot save {self.path}: {e.strerror}", file=sys.stderr)  # never the contents
