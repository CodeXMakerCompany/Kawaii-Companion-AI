from kawaii.body.body import Body
from kawaii.voice.banner import VoiceBanner
from tests.fakes import make_screen


class FakeAssistant:
    def __init__(self):
        self.state, self.events, self.toggles, self.ticks = "idle", [], 0, 0

    def toggle(self):
        self.toggles += 1

    def tick(self):
        self.ticks += 1

    def poll(self):
        events, self.events = self.events, []
        return events


class FakeSpeaker:
    def __init__(self, available=True):
        self.available, self.said, self.stops = available, [], 0

    def react(self, kind, **fields):
        self.said.append((kind, fields))
        return kind

    def stop(self):
        self.stops += 1


class FakeMover:
    def __init__(self):
        self.expected = []

    def expect(self, output, **kw):
        self.expected.append((output, kw))


def make(available=True):
    assistant, speaker, body, mover = FakeAssistant(), FakeSpeaker(available), Body(), FakeMover()
    banner = VoiceBanner(make_screen(), assistant, speaker, body, mover, app_output=lambda: "DP-1")
    return banner, assistant, speaker, body, mover


def feed(banner, assistant, *events, now=0.0, state=None):
    if state:
        assistant.state = state
    assistant.events.extend(events)
    banner.tick(now)


def test_shows_what_she_heard_then_what_ran():
    banner, a, speaker, _, _ = make()
    feed(banner, a, ("heard", "open firefox"))
    assert banner.text == "“open firefox”"
    feed(banner, a, ("run", "firefox &", "Opening Firefox", {"kind": "open", "app": "Firefox"}), now=1.0)
    assert banner.text == "“open firefox”: Opening Firefox  ($ firefox &)"
    assert banner.until == 7.0
    assert speaker.said[-1] == ("open", {"app": "Firefox"})


def test_opened_apps_go_to_your_monitor():
    banner, a, _, _, mover = make()
    feed(banner, a, ("run", "x", "X", {"kind": "open", "app": "X"}))
    assert mover.expected == [("DP-1", {"seconds": 15, "lookback": 4})]


def test_learned_commands_use_their_own_reaction():
    banner, a, speaker, _, _ = make()
    feed(banner, a, ("run", "systemctl poweroff", "Bye", {"react": "poweroff"}))
    assert speaker.said[-1] == ("poweroff", {})
    feed(banner, a, ("run", "ls", "Listed", {}))
    assert speaker.said[-1] == ("ran", {})


def test_without_a_voice_she_still_moves_her_mouth():
    banner, a, _, body, _ = make(available=False)
    feed(banner, a, ("run", "ls", "Listed", {}))
    assert body.talk_left() == 2


def test_ai_suggestion_waits_for_run_or_cancel():
    banner, a, speaker, _, _ = make()
    feed(banner, a, ("heard", "clean docker"))
    feed(banner, a, ("confirm", "docker system prune", "Prune docker", {"kind": "ai"}), state="confirm")
    assert banner.command == "docker system prune" and banner.ai
    assert banner.text == "AI suggests for “clean docker”: Prune docker"
    assert speaker.said[-1] == ("confirm_ai", {})
    feed(banner, a, ("error", "Didn't catch that", {"kind": "not_heard"}))
    assert banner.command == "docker system prune"  # still waiting on you


def test_confirm_commands_say_their_own_line():
    banner, a, speaker, _, _ = make()
    feed(banner, a, ("heard", "apaga la pc"))
    feed(banner, a, ("confirm", "./poweroff.sh", "Turn off the PC", {"react": "poweroff"}), state="confirm")
    assert banner.text == "“apaga la pc”: Turn off the PC?"
    assert speaker.said[-1] == ("confirm_poweroff", {})


def test_errors_show_red_and_hide_later():
    banner, a, speaker, _, _ = make()
    feed(banner, a, ("error", "Firefox is not open", {"kind": "not_open", "app": "Firefox"}), now=2.0)
    assert banner.error and banner.until == 8.0
    assert speaker.said[-1] == ("not_open", {"app": "Firefox"})
    banner.tick(8.0)
    assert banner.text is None


def test_never_records_her_own_voice():
    banner, a, speaker, _, _ = make()
    feed(banner, a, ("status", "Listening…"), state="listening")
    assert speaker.stops == 1


def test_dances_while_thinking_and_leaves_your_dance_alone():
    banner, a, _, body, _ = make()
    feed(banner, a, state="thinking")
    assert body.dancer.active
    feed(banner, a, state="idle")
    assert not body.dancer.active
    body.toggle(body.dancer)
    feed(banner, a, state="thinking")
    feed(banner, a, state="idle")
    assert body.dancer.active


def test_global_shortcut_toggles_listening_on_the_next_frame():
    banner, a, _, _, _ = make()
    banner.request_toggle()
    assert a.toggles == 0
    banner.tick(0.0)
    banner.tick(0.1)
    assert a.toggles == 1
