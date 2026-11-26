from pathlib import Path
from types import SimpleNamespace

from kawaii.cards.base import Deck
from kawaii.cards.picker import PickerCard
from kawaii.input.keys import BTN_LEFT, KEY_BACKSPACE, KEY_ENTER
from tests.fakes import make_screen

HOME = Path("/home/me")
PROJECTS = HOME / "Projects"


class FakeRepos:
    START = PROJECTS

    @staticmethod
    def folders(path):
        return {PROJECTS: [("app", True), ("notes", False)], PROJECTS / "notes": []}.get(path, [])

    @staticmethod
    def branches(repo):
        return [("main", False), ("feature/login", True), ("fix/typo", False)], "main"


class FakeReviewer:
    def __init__(self):
        self.busy, self.started, self.outcome = False, None, None

    def start(self, repo, branch, base):
        self.started = (repo, branch, base)

    def poll(self):
        outcome, self.outcome = self.outcome, None
        return outcome


class FakeMover:
    def __init__(self):
        self.expected = None

    def expect(self, output, **kw):
        self.expected = (output, kw)


def make():
    screen = make_screen({("pk_open", None): (0, 0, 10, 10)})
    card = PickerCard(screen, FakeReviewer(), FakeMover(), app_output=lambda: "DP-1", head=lambda: (0, 0),
                      repos=FakeRepos, home=HOME, is_dir=lambda p: True)
    deck = Deck(card)
    deck.show("picker")
    return screen, card, deck


def test_opens_on_projects():
    _, card, _ = make()
    assert card.step == "folder" and card.path == PROJECTS
    assert card.items() == [("up", None), ("dir", ("app", True)), ("dir", ("notes", False))]


def test_folders_browse_and_backspace_goes_up():
    _, card, deck = make()
    deck.click(("pk_row", 2), BTN_LEFT, None)
    assert card.path == PROJECTS / "notes"
    deck.key(KEY_BACKSPACE, False)
    assert card.path == PROJECTS


def test_never_browses_above_home():
    _, card, deck = make()
    card.path = HOME
    deck.click(("pk_row", 0), BTN_LEFT, None)
    assert card.path == HOME


def test_a_repo_lists_its_branches_with_the_current_one_selected():
    _, card, deck = make()
    deck.click(("pk_row", 1), BTN_LEFT, None)
    assert card.step == "branch" and card.repo == PROJECTS / "app"
    assert card.selected == "feature/login" and card.base == "main"


def test_typing_filters_branches_and_selects_the_first_match():
    _, card, deck = make()
    deck.click(("pk_row", 1), BTN_LEFT, None)
    deck.text("fix")
    assert card.items() == [("branch", "fix/typo")] and card.selected == "fix/typo"
    deck.key(KEY_BACKSPACE, False)
    deck.key(KEY_BACKSPACE, False)
    deck.key(KEY_BACKSPACE, False)
    assert card.filter == ""
    deck.key(KEY_BACKSPACE, False)
    assert card.step == "folder"


def test_enter_hands_the_review_to_kiro_on_your_monitor():
    _, card, deck = make()
    deck.click(("pk_row", 1), BTN_LEFT, None)
    deck.key(KEY_ENTER, False)
    assert card.reviewer.started == (PROJECTS / "app", "feature/login", "main")
    assert card.mover.expected == ("DP-1", {"app": "kiro", "title": "app", "seconds": 45})
    assert card.status == "Opening Kiro…"


def test_closes_itself_a_moment_after_kiro_opened():
    screen, card, deck = make()
    card.reviewer.outcome = (True, "Prompt typed in")
    deck.tick(10.0)
    assert card.status == "Prompt typed in" and card.is_open
    screen.fx.idea.assert_called_once()
    deck.tick(13.6)
    assert not card.is_open


def test_failure_stays_open():
    _, card, deck = make()
    card.reviewer.outcome = (False, "Kiro is not installed")
    deck.tick(10.0)
    deck.tick(20.0)
    assert card.is_open and card.status == "Kiro is not installed"
