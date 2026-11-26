"""Business Rules, per company: the list of companies, then one company's numbered rules,
ready to paste into a prompt. Enter opens the company / adds the rule, click copies a rule,
right-click removes, Ctrl+C copies all, Ctrl+V pastes, Esc goes back (then closes)."""

from kawaii.cards.base import Card, clamp_skip
from kawaii.input.keys import BTN_LEFT, BTN_RIGHT, ENTER, KEY_BACKSPACE, KEY_C, KEY_ESC, KEY_V
from kawaii.input.textfield import erase, printable

NO_CLIPBOARD = "Install wl-clipboard to copy and paste"


class RulesCard(Card):
    name = "rules"
    opener = ("button", "rules")
    open_fx = "pop"
    hits = ("rules_add", "rules_paste", "rules_copy", "rules_back", "rules_done", "rules_row")
    scroll_hits = ("rules_card", "rules_row", "rules_input")

    def __init__(self, screen, rulebook, clipboard):
        super().__init__(screen)
        self.rulebook, self.clipboard = rulebook, clipboard
        self.company = None  # index of the company opened, None: the list of companies
        self.draft = ""  # the company name or rule being typed
        self.status = ""  # a short note: Copied!, why paste failed
        self.skip = 0  # rows scrolled past (None: down to the newest rule)

    def _reset(self):
        self.open_company(None)

    opened = closed = _reset

    def open_company(self, index):
        self.company, self.draft, self.skip, self.status = index, "", 0, ""
        self.screen.redraw()

    def add(self, rect=None):
        """In the list: opens the company typed (adding it if new); inside one: adds the rule."""
        if self.company is None:
            index = self.rulebook.add_company(self.draft)
            if index is None:
                self.status = "Type a company name first"
                self.screen.redraw()
                return
            self.open_company(index)
        elif self.rulebook.add_rule(self.company, self.draft):
            self.draft, self.status, self.skip = "", "", None  # None: scrolled to the new one
        else:
            self.status = "Write the rule first"
        if rect:
            self.fx.done(rect)
        self.screen.redraw()

    def paste(self):
        if not self.clipboard.available:
            self.status = NO_CLIPBOARD
        elif not (text := (self.clipboard.get() or "").strip()):
            self.status = "The clipboard has no text"
        else:
            self.draft += " ".join(text.split())
            self.status = ""
        self.screen.redraw()

    def copy(self, index=None):
        """One rule, or (index None) the whole numbered list."""
        if not self.clipboard.available:
            self.status = NO_CLIPBOARD
            self.screen.redraw()
            return False
        ci = self.company
        text = self.rulebook.as_text(ci) if index is None else self.rulebook.companies[ci]["rules"][index]["text"]
        ok = self.clipboard.set(text)
        self.status = "Copied!" if ok else "Could not copy"
        self.screen.redraw()
        return ok

    def click(self, hit, button, rect):
        kind = hit[0]
        if kind == "rules_row":
            if button == BTN_RIGHT:
                self.fx.scrap(rect)
                if self.company is None:
                    self.rulebook.remove_company(hit[1])
                else:
                    self.rulebook.remove_rule(self.company, hit[1])
                self.screen.overlay.hover = None
                self.screen.redraw()
            elif button == BTN_LEFT:
                if self.company is None:
                    self.open_company(hit[1])
                    self.fx.pop(rect)
                elif self.copy(hit[1]):
                    self.fx.pick(rect)
            return
        if button != BTN_LEFT:
            return
        self.screen.press(hit)
        if kind == "rules_add":
            self.add(rect)
        elif kind == "rules_paste":
            self.paste()
        elif kind == "rules_copy":
            if self.copy():
                self.fx.pick(rect)
        elif kind == "rules_back":
            self.open_company(None)
        else:
            self.close()

    def key(self, key, ctrl):
        if key == KEY_ESC:
            self.open_company(None) if self.company is not None else self.close()
        elif key in ENTER:
            self.add(self.screen.rect("rules_add"))
        elif key == KEY_V and ctrl:
            self.paste()
        elif key == KEY_C and ctrl and self.company is not None:
            hit = self.screen.under_mouse()
            self.copy(hit[1] if hit and hit[0] == "rules_row" else None)
        elif key == KEY_BACKSPACE and self.draft:
            self.draft = erase(self.draft, word=ctrl)
            self.screen.redraw()
        return True

    def text(self, text):
        typed = printable(text)
        if typed:
            self.draft += typed
            self.screen.redraw()
            self.screen.caret_dust()

    def scroll(self, steps):
        # From what is drawn: skip may be None (scrolled to the newest rule).
        self.skip = clamp_skip(self.screen.overlay.rules_skip, steps, self.screen.overlay.rules_rows)
        self.screen.redraw()

    def payload(self):
        return {"open": self.is_open, "companies": self.rulebook.companies, "company": self.company,
                "draft": self.draft, "status": self.status, "skip": self.skip}
