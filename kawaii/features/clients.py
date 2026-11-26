"""Clients: who you are working for. Each client has its own folder of data (pendings,
reminders, endpoints, vault) under <config>/clients/<slug>/, and Business Rules opens on
that client's rules. Picking a client shows only that client's data.

The list and the current client are saved in <config>/clients.json. Removing a client only
takes it off the list: its folder stays, and adding it again brings its data back.

The first start with clients moves what you had before into a client called General (the
old files stay where they were, as a backup) and makes each Business Rules company a client.
"""

import json
import re
import shutil
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

GENERAL = "General"
LEGACY = ("pendings.json", "events.json", "observe.json", "vault.txt")


def slug(name):
    """A safe folder name for a client: lowercase ASCII letters, digits and dashes."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-") or "client"


@dataclass
class Space:
    """Where one client's data lives."""
    name: str
    folder: Path

    @property
    def pendings(self):
        return self.folder / "pendings.json"

    @property
    def events(self):
        return self.folder / "events.json"

    @property
    def observe(self):
        return self.folder / "observe.json"

    @property
    def vault(self):
        return self.folder / "vault.txt"


class Clients:
    def __init__(self, config_dir):
        self.config_dir = Path(config_dir)
        self.file = self.config_dir / "clients.json"
        self.names, self.current = [], None
        try:
            saved = json.loads(self.file.read_text(encoding="utf-8"))
            self.names = [n for n in saved.get("clients", []) if isinstance(n, str) and n.strip()]
            self.current = saved.get("current") if saved.get("current") in self.names else None
        except (OSError, ValueError):
            self._first_start()
        if not self.names:
            self.names = [GENERAL]
        if self.current is None:
            self.current = self.names[0]
            self.save()

    def find(self, name):
        name = " ".join(name.split()).lower()
        return next((n for n in self.names if n.lower() == name), None)

    def add(self, name):
        """The client called `name` (added if new), or None for a blank name."""
        name = " ".join(name.split())
        if not name:
            return None
        found = self.find(name)
        if found:
            return found
        self.names.append(name)
        self.save()
        return name

    def select(self, name):
        if name in self.names:
            self.current = name
            self.save()

    def remove(self, name):
        """Off the list (its data stays); never the client you are in."""
        if name == self.current or name not in self.names:
            return False
        self.names.remove(name)
        self.save()
        return True

    def space(self, name):
        return Space(name, self.config_dir / "clients" / slug(name))

    def _first_start(self):
        """Move what was there before clients into General; Business Rules companies become clients."""
        general = self.space(GENERAL)
        general.folder.mkdir(parents=True, exist_ok=True)
        for name in LEGACY:
            old, new = self.config_dir / name, general.folder / name
            if old.exists() and not new.exists():
                shutil.copy2(old, new)  # copy2 keeps the vault readable by you only
        self.names, self.current = [GENERAL], GENERAL
        try:
            companies = json.loads((self.config_dir / "rules.json").read_text(encoding="utf-8")).get("companies", [])
        except (OSError, ValueError):
            companies = []
        for c in companies:
            if isinstance(c, dict) and str(c.get("name", "")).strip() and not self.find(c["name"]):
                self.names.append(" ".join(c["name"].split()))
        self.save()

    def save(self):
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            self.file.write_text(json.dumps({"clients": self.names, "current": self.current}, indent=1,
                                            ensure_ascii=False), encoding="utf-8")
        except OSError as e:
            print(f"clients: cannot save {self.file}: {e}", file=sys.stderr)
