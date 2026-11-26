"""Vault: API keys and temporary tokens at hand, each under the reason you keep it. Type a
reason, Enter opens it (new or not); inside, type the key's name, Enter, then paste or type
the key, Enter adds it (Temp 24h: it deletes itself after a day). Click a key to copy it:
the clipboard is cleared again after CLEAR_AFTER seconds. Right-click removes, Esc goes back
(then closes). Keys are only ever shown masked."""

from kawaii.cards.base import Card, clamp_skip
from kawaii.features.vault import Vault, mask
from kawaii.input.keys import BTN_LEFT, BTN_RIGHT, ENTER, KEY_BACKSPACE, KEY_ESC, KEY_TAB, KEY_V
from kawaii.input.textfield import erase, printable

CLEAR_AFTER = 45  # seconds a copied key stays on the clipboard
NO_CLIPBOARD = "Install wl-clipboard to copy and paste"


def time_left(seconds):
    return f"{int(seconds // 3600)}h" if seconds >= 3600 else f"{max(1, int(seconds // 60))}m"


class VaultCard(Card):
    name = "vault"
    opener = ("button", "vault")
    open_fx = "pop"
    hits = ("vault_add", "vault_paste", "vault_back", "vault_done", "vault_temp", "vault_row", "vault_name_in",
            "vault_key_in", "vault_input")
    scroll_hits = ("vault_card", "vault_row")
    needs_client = True

    def __init__(self, screen, vault, clipboard):
        super().__init__(screen)
        self.vault, self.clipboard = vault, clipboard
        self.reason = None  # index of the reason opened, None: the list of reasons
        self.draft = ""  # the reason being typed (in the list)
        self.key_name = ""  # the key's name being typed (inside a reason)
        self.secret = ""  # the key being typed or pasted (never drawn, only dots)
        self.focus = "name"  # inside a reason: which field typing goes to, name or secret
        self.temporary = False  # the key being added deletes itself after a day
        self.status = ""
        self.skip = 0
        self.copied = None  # the key last copied, until the clipboard is cleared
        self.clear_at = None
        self.purge_at = 0.0

    def _reset(self):
        self.open_reason(None)

    opened = closed = _reset

    def client_changed(self, space):
        self.vault = Vault(space.vault)
        self._reset()

    def open_reason(self, index):
        self.reason, self.draft, self.key_name, self.secret = index, "", "", ""
        self.focus, self.temporary, self.skip, self.status = "name", False, 0, ""
        self.screen.redraw()

    def _field(self):
        if self.reason is None:
            return "draft"
        return "secret" if self.focus == "secret" else "key_name"

    def add(self, rect=None):
        """In the list: opens the reason typed (adding it if new); inside one: adds the key."""
        if self.reason is None:
            index = self.vault.add_reason(self.draft)
            if index is None:
                self.status = "Type a reason first"
            else:
                self.open_reason(index)
                if rect:
                    self.fx.pop(rect)
        elif not self.key_name.strip():
            self.focus, self.status = "name", "Name the key first"
        elif not self.secret.strip():
            self.focus, self.status = "secret", "Paste or type the key too"
        elif self.vault.add_key(self.reason, self.key_name, self.secret, self.temporary):
            temp = self.temporary
            self.key_name, self.secret, self.focus, self.temporary = "", "", "name", False
            self.status = "Saved · deletes itself in 24h" if temp else "Saved"
            if rect:
                self.fx.done(rect)
        self.screen.redraw()

    def paste(self):
        if not self.clipboard.available:
            self.status = NO_CLIPBOARD
        elif not (text := (self.clipboard.get() or "").strip()):
            self.status = "The clipboard has no text"
        else:
            field = self._field()
            pasted = "".join(text.split()) if field == "secret" else " ".join(text.split())
            setattr(self, field, getattr(self, field) + pasted)
            self.status = ""
        self.screen.redraw()

    def copy(self, index):
        if not self.clipboard.available:
            self.status = NO_CLIPBOARD
            self.screen.redraw()
            return False
        key = self.vault.reasons[self.reason]["keys"][index]
        ok = self.clipboard.set(key["secret"])
        if ok:
            self.copied, self.clear_at = key["secret"], None  # the clock starts at the next frame
            self.status = f"Copied {key['name']} · clears in {CLEAR_AFTER}s"
        else:
            self.status = "Could not copy"
        self.screen.redraw()
        return ok

    def click(self, hit, button, rect):
        kind = hit[0]
        if kind == "vault_row":
            if button == BTN_RIGHT:
                self.fx.scrap(rect)
                if self.reason is None:
                    self.vault.remove_reason(hit[1])
                else:
                    self.vault.remove_key(self.reason, hit[1])
                self.screen.overlay.hover = None
                self.screen.redraw()
            elif button == BTN_LEFT:
                if self.reason is None:
                    self.open_reason(hit[1])
                    self.fx.pop(rect)
                elif self.copy(hit[1]):
                    self.fx.pick(rect)
            return
        if button != BTN_LEFT:
            return
        if kind in ("vault_name_in", "vault_key_in"):
            self.focus = "name" if kind == "vault_name_in" else "secret"
            self.screen.redraw()
            return
        if kind == "vault_input":
            return
        self.screen.press(hit)
        if kind == "vault_add":
            self.add(rect)
        elif kind == "vault_paste":
            self.paste()
        elif kind == "vault_temp":
            self.temporary = not self.temporary
            self.screen.redraw()
        elif kind == "vault_back":
            self.open_reason(None)
        else:
            self.close()

    def key(self, key, ctrl):
        if key == KEY_ESC:
            self.open_reason(None) if self.reason is not None else self.close()
        elif key == KEY_TAB and self.reason is not None:
            self.focus = "secret" if self.focus == "name" else "name"
            self.screen.redraw()
        elif key in ENTER:
            if self.reason is not None and self.focus == "name" and not self.secret.strip():
                self.focus = "secret"
                self.screen.redraw()
            else:
                self.add(self.screen.rect("vault_add"))
        elif key == KEY_V and ctrl:
            self.paste()
        elif key == KEY_BACKSPACE and getattr(self, self._field()):
            field = self._field()
            setattr(self, field, erase(getattr(self, field), word=ctrl and field != "secret"))
            self.screen.redraw()
        return True

    def text(self, text):
        typed = printable(text)
        field = self._field()
        if field == "secret":
            typed = "".join(typed.split())  # keys have no spaces
        if typed:
            setattr(self, field, getattr(self, field) + typed)
            self.screen.redraw()
            if field != "secret":
                self.screen.caret_dust()

    def scroll(self, steps):
        self.skip = clamp_skip(self.skip, steps, self.screen.overlay.vault_rows)
        self.screen.redraw()

    def tick(self, now):
        if now >= self.purge_at:  # temporary keys whose day is over
            self.purge_at = now + 30
            if self.vault.purge():
                if self.reason is not None and self.reason >= len(self.vault.reasons):
                    self.reason = None
                self.screen.redraw()
        if self.copied is None:
            return
        if self.clear_at is None:
            self.clear_at = now + CLEAR_AFTER
        elif now >= self.clear_at:
            if self.clipboard.get() == self.copied:  # unless you copied something else since
                self.clipboard.clear()
                self.status = "Clipboard cleared"
                self.screen.redraw()
            self.copied = self.clear_at = None

    def payload(self):
        """What the overlay draws: names, counts and masked keys, never a key itself."""
        reasons = [{"name": r["name"], "count": len(r["keys"])} for r in self.vault.reasons]
        keys = []
        if self.reason is not None:
            now = self.vault.now()
            keys = [{"name": k["name"], "masked": mask(k["secret"]),
                     "expires_in": time_left(k["expires"] - now) if k["expires"] else None}
                    for k in self.vault.reasons[self.reason]["keys"]]
        return {"open": self.is_open, "count": self.vault.count, "reasons": reasons, "reason": self.reason,
                "keys": keys, "draft": self.draft, "name": self.key_name,
                "secret_dots": "•" * min(len(self.secret), 24), "focus": self.focus, "temporary": self.temporary,
                "status": self.status, "skip": self.skip}
