"""The overlay app: builds every part, then runs the frame loop that ties them together.

Each frame: apply a pending resize, animate her (body routines, voice, mouth), draw the
model, measure her pixels when due, let the background watchers report (agents, PRs,
endpoints, reminders), play the effects that follow what she is doing, repaint the UI
layer if anything changed, and resend the input region.
"""

import contextlib
import io
import os
import random
import signal
import time

os.environ.setdefault("PYOPENGL_PLATFORM", "egl")  # must precede any OpenGL import

import OpenGL  # noqa: E402
from OpenGL import EGL  # noqa: E402, F401  PyOpenGL's EGL module breaks if imported after the next line

OpenGL.ERROR_CHECKING = False  # PyOpenGL checks glGetError after every GL call otherwise
from OpenGL import GL  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):  # live2d-py prints a banner on import
    import live2d

from kawaii import paths  # noqa: E402
from kawaii.alerts import Alerts  # noqa: E402
from kawaii.body.body import Body  # noqa: E402
from kawaii.body.expressions import Expressions  # noqa: E402
from kawaii.body.reactions import AgentReactions  # noqa: E402
from kawaii.body.walk import Walker  # noqa: E402
from kawaii.cards.base import Deck, Screen  # noqa: E402
from kawaii.cards.calendar import CalendarCard  # noqa: E402
from kawaii.cards.decoder import DecoderCard  # noqa: E402
from kawaii.cards.observe import ObserveCard  # noqa: E402
from kawaii.cards.pendings import PendingsCard  # noqa: E402
from kawaii.cards.picker import PickerCard  # noqa: E402
from kawaii.cards.prs import PRCard  # noqa: E402
from kawaii.cards.rules import RulesCard  # noqa: E402
from kawaii.cards.settings import SettingsCard  # noqa: E402
from kawaii.features import decode, prreview  # noqa: E402
from kawaii.features.agents import WAITING, WATCHERS, WORKING  # noqa: E402
from kawaii.features.observe import Pinger  # noqa: E402
from kawaii.features.pendings import Pendings  # noqa: E402
from kawaii.features.prwatch import PRWatcher  # noqa: E402
from kawaii.features.reminders import Events  # noqa: E402
from kawaii.features.rules import Rulebook  # noqa: E402
from kawaii.features.sysmon import SystemMonitor  # noqa: E402
from kawaii.input.clipboard import Clipboard  # noqa: E402
from kawaii.input.keys import load_hotkeys  # noqa: E402
from kawaii.input.router import Router  # noqa: E402
from kawaii.layout.geometry import clamp_size  # noqa: E402
from kawaii.layout.layout import DEFAULT_MARGIN, Layout  # noqa: E402
from kawaii.layout.spots import Spots  # noqa: E402
from kawaii.monitor_panel import MonitorPanel  # noqa: E402
from kawaii.process import animations_enabled, replace_running_copy  # noqa: E402
from kawaii.render.fx import Effects  # noqa: E402
from kawaii.render.gl import OverlayTexture, read_alpha, write_snapshot  # noqa: E402
from kawaii.render.overlay import Overlay  # noqa: E402
from kawaii.render.painter import NOTES_H, PANEL_W  # noqa: E402
from kawaii.settings import StateStore  # noqa: E402
from kawaii.voice.announce import endpoint_down, pr_news  # noqa: E402
from kawaii.voice.assistant import VoiceAssistant, openrouter  # noqa: E402
from kawaii.voice.banner import VoiceBanner  # noqa: E402
from kawaii.voice.speech import Speaker  # noqa: E402
from kawaii.wayland.window import LayerWindow  # noqa: E402
from kawaii.wayland.winmove import WindowMover  # noqa: E402


class App:
    def __init__(self, args):
        self.args = args
        if not (args.snapshot or args.allow_multiple):
            replace_running_copy()  # before reading state, so the old copy's last save is included
        self.store = store = StateStore(paths.STATE_FILE)
        default_size = clamp_size(*(int(v) for v in args.size.lower().split("x"))) if args.size else (420, 620)
        saved = store.layout_for(store.get("output")) or {}
        size = saved.get("model_size", default_size)
        left = saved.get("left", PANEL_W)

        self.win = win = LayerWindow(left + size[0], NOTES_H + size[1], saved.get("margin", DEFAULT_MARGIN),
                                     output_name=store.get("output"))
        live2d.enableLog(False)
        live2d.init()
        live2d.glInit()
        self.model = model = live2d.Model()
        model.LoadModelJson(str(args.model))
        model.Resize(*size)
        model.SetAutoBlink(True)
        model.SetAutoBreath(True)
        self.hotkeys = load_hotkeys(args.model.parent / "hotkeys.json")
        self.expressions = Expressions(model)
        self.layout = Layout(model, win, store, left=left, size=size, default_size=default_size,
                             fixed_scale=args.scale, snapshot=bool(args.snapshot))

        # The UI layer and the effects drawn over it.
        self.overlay = Overlay(size[0], size[1], 1.0, left)  # the Moves grid (moves.json) is hidden; hotkeys still toggle them
        self.overlay_tex = OverlayTexture(win.width, win.height)
        self.monitor_tex = OverlayTexture(1, 1)  # the monitor's own small layer: its numbers change every 2s
        self.fx_tex = OverlayTexture(1, 1)  # the effects' layer, only drawn while one is alive
        self.fx = Effects(enabled=not args.no_fx and animations_enabled())
        self.screen = Screen(self.overlay, self.fx)
        self.spots = Spots(self.layout, self.overlay, win)
        self.body = Body(on_toggle=self._routines_changed)
        self.reactions = AgentReactions(self.body)

        # Background watchers and services.
        self.monitor = SystemMonitor()
        self.panel = MonitorPanel(self.monitor, store)
        self.events = Events(paths.EVENTS_FILE)
        self.alerts = Alerts(self.events, self.monitor)
        self.assistant = VoiceAssistant(paths.APP_DIR, paths.CONFIG_DIR)
        self.speaker = Speaker(paths.DATA_DIR / "kokoro", paths.CACHE_DIR / "tts", paths.ASSETS / "voice_lines.json")
        if not args.snapshot:
            self.speaker.prerender()  # her fixed lines, generated once in the background
        self.agent_apps = [W() for W in WATCHERS]  # Kiro, Claude
        self.badges = {}  # app name -> its floating icon, while the app is open
        self.prs = PRWatcher(paths.CONFIG_DIR / "prwatch.json")
        self.pinger = Pinger(paths.CONFIG_DIR / "observe.json")  # the Observability endpoints
        self.gh_icon = paths.CONFIG_DIR / "github.png"  # optional: your own GitHub icon; a pull-request symbol otherwise
        self.mover = WindowMover()  # puts the windows of apps she opens on the monitor you chose
        explainer = decode.Explainer(lambda system, text: openrouter(
            self.assistant.key_file, self.assistant.models, system, text, max_tokens=350))

        # The cards above her head, one open at a time.
        clipboard, head = Clipboard(), self.spots.head
        settings = SettingsCard(self.screen, store, self.mover, here=lambda: win.output.name if win.output else None)
        self.deck = Deck(
            PendingsCard(self.screen, Pendings(paths.PENDINGS_FILE), on_change=lambda: self.layout.refresh_silhouette(0.7)),
            CalendarCard(self.screen, self.events, self.alerts),
            DecoderCard(self.screen, clipboard, explainer, self.body, head),
            PickerCard(self.screen, prreview.Reviewer(), self.mover, settings.app_output, head),
            ObserveCard(self.screen, self.pinger, clipboard),
            RulesCard(self.screen, Rulebook(paths.CONFIG_DIR / "rules.json"), clipboard),  # Business Rules, per company
            PRCard(self.screen, self.prs),
            settings,
        )
        self.voice = VoiceBanner(self.screen, self.assistant, self.speaker, self.body, self.mover, settings.app_output)

        self.moves_open = store.get("moves_open", True)  # mini move buttons expanded
        self.flash_until = None  # end of a button's inverted impact frame
        self.pose_seen = None  # last pose label, to flash on each new pose
        self.next_pulse = 0.0  # mic ring while listening
        self.next_rumble = 0.0  # ゴゴゴゴ while dancing
        self.next_step = 0.0  # dust while walking
        self.walk_x = 0.0
        self.gh_hop_until = 0.0  # the GitHub badge hops until then (new comments just came in)

        self.router = Router(self)
        # Ctrl+C, kill and a closing terminal all end the loop normally (state saved, GL torn
        # down in order) instead of dying mid-frame.
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(sig, self._request_quit)
        signal.signal(signal.SIGUSR1, lambda signum, frame: self.voice.request_toggle())

        if args.pendings:
            self.deck.show("pendings")
        if win.output:
            self.layout.apply(win.output)
        else:
            self.layout.request_fit(0.3)

    # -- small things the parts ask for

    def _request_quit(self, signum, frame):
        self.win.closed = True

    def _routines_changed(self):
        self.screen.dirty = self.screen.region_dirty = True

    def toggle_expression(self, exp):
        self.expressions.toggle(exp)
        self.screen.redraw()
        self.layout.refresh_silhouette(0.6)  # poses, chibi and outfit change her outline

    def impact_frame(self, hit):
        """The button turns inside out for an instant, then springs back."""
        self.overlay.flash = hit
        self.flash_until = time.perf_counter() + 0.19

    def react(self, kind, silent_seconds, **fields):
        """She says a line; with no voice she at least moves her mouth."""
        said = self.speaker.react(kind, **fields)
        if not (said and self.speaker.available):
            self.body.talk(silent_seconds)

    def greet_if_free(self):
        if not self.body.busy:
            self.body.toggle(self.body.greeter)  # 'hey!' with a wave

    # -- the frame loop

    def run(self):
        args, win = self.args, self.win
        last = next_frame = time.perf_counter()
        snapshot_at = last + 2.5 if args.snapshot else None
        while not win.closed:
            now = time.perf_counter()
            if now < next_frame:
                win.pump(next_frame - now)
                continue
            # Smooth 60 fps while being dragged or resized, the normal cap otherwise.
            frame = 1.0 / (max(args.fps, 60) if self.layout.drag or self.fx.busy else args.fps)
            next_frame += frame
            if next_frame < now:  # fell behind (suspend, stall): resync instead of bursting
                next_frame = now + frame
            dt, last = now - last, now

            self._apply_geometry()
            self._animate(now, dt)
            motion = self._move_body(dt)
            self._draw_model(now)
            self._watch(now)
            self._follow_with_effects(now, dt, motion)
            self._paint()
            self._draw_layers(dt)
            self._update_input_region()
            if snapshot_at and now >= snapshot_at:
                write_snapshot(args.snapshot, win.width, win.height)
                break
            win.swap()

        self.layout.remember()
        self.model = self.layout.model = None
        live2d.dispose()
        win.destroy()

    def _apply_geometry(self):
        if self.layout.apply_pending_geometry():
            (mw, mh), left = self.layout.size, self.layout.left
            self.overlay.resize(mw, mh, left)
            self.overlay_tex.resize(self.win.width, self.win.height)
            self.screen.redraw()

    def _animate(self, now, dt):
        """Idle motion, the voice assistant, the system monitor, reminders and alarms."""
        if self.model.IsMotionFinished():
            self.model.StartRandomMotion("Idle", live2d.MotionPriority.IDLE)
        self.model.Update(dt)
        self.voice.tick(now)
        sampled, layout_changed = self.panel.tick(now)
        if sampled:
            self.alerts.recheck()
        if layout_changed:  # click areas moved: the main layer must know
            self.screen.redraw()
        appeared, changed, nag = self.alerts.tick(now)
        if appeared:
            self.screen.after(lambda: self.overlay.rect_of("alert") and self.fx.land(self.overlay.rect_of("alert")))
        if changed:
            self.screen.redraw()
        if nag:
            self._nag()

    def _nag(self):
        """Get attention: a greeting (unless she is busy) and she says what is waiting."""
        self.greet_if_free()
        said, first = None, self.alerts.announcement()
        if first:
            kind, value = first
            if kind == "alarm":
                said = self.speaker.lines.get("alarms", {}).get(value)
                if said:
                    self.speaker.say(said)
            else:
                said = self.speaker.react(kind, title=value)
        if not (said and self.speaker.available):
            self.body.talk(3)
        bubble = self.overlay.rect_of("alert") or self.overlay.rect_of("monitor_toggle")
        if bubble:
            self.fx.nudge(bubble)
        self.screen.redraw()

    def _move_body(self, dt):
        motion = self.body.update(self.model, dt, hand_up=self.deck["pendings"].is_open, room=self.layout.room(),
                                  offset=self.layout.offset, voice_mouth=self.speaker.mouth(time.monotonic()))
        if motion.settled:  # back at rest: measure her real outline again
            self.layout.refresh_silhouette(0.1)
        if motion.changed:  # button states / pose label changed
            self._routines_changed()
        if motion.talk_changed:  # countdown tick, or she just stopped
            self.screen.redraw()
        return motion

    def _draw_model(self, now):
        layout = self.layout
        mw, mh = layout.size
        live2d.clearBuffer(0.0, 0.0, 0.0, 0.0)
        GL.glViewport(layout.left, 0, mw, mh)  # her area is the bottom-right block
        self.model.Draw()
        # Measurements from her pixels, before the UI is drawn on top.
        if layout.measurement_due(now, still=not layout.drag and not self.body.moving):
            if layout.measure(read_alpha(layout.left, mw, mh), now):
                self.screen.region_dirty = True
                if layout.head_y != self.overlay.head_y:  # buttons and the list follow her head
                    self.overlay.head_y = layout.head_y
                    self.screen.redraw()

    # -- background watchers

    def _watch(self, now):
        working, waiting = self._watch_agents(now)
        for event in self.reactions.update(now, working, waiting):
            if event == "puzzled":
                self.fx.later(0.5, lambda: self.fx.puzzled(*self.spots.head(), self.body.huh.side))
            else:  # "aha": the agents are done
                self.fx.later(0.15, lambda: self.fx.idea(*self.spots.head(), self.body.thinker.side))
        self.deck.tick(now)  # the PR review handed to Kiro, the stack trace explanation
        self._watch_prs(now)
        self._watch_endpoints(now)

    def _watch_agents(self, now):
        """Each agent app's icon floats by her head while it is open, its dots circling
        while an agent works there. Returns the icon sides working / waiting on you."""
        working, waiting = [], []
        for app in self.agent_apps:
            is_open, doing = app.poll(now)
            badge = self.badges.get(app.name)
            if is_open and not badge:
                badge = self.badges[app.name] = self.fx.badge(app.icon, lambda side=app.side: self.spots.agent(side))
            elif not is_open and badge:
                badge.leave()
                badge = self.badges.pop(app.name) and None
            if badge:
                if badge.working and doing not in (WORKING, WAITING):  # this one is done
                    self.fx.kira(*self.spots.agent(app.side), r=12, life=0.7)
                badge.working, badge.waiting = doing in (WORKING, WAITING), doing == WAITING
            if doing == WORKING:
                working.append(app.side)
            elif doing == WAITING:
                waiting.append(app.side)
        return working, waiting

    def _watch_prs(self, now):
        """gh checks every 15 minutes in the background. New comments by others bring up the
        GitHub badge with their count and she says what happened; the badge stays until you
        open the comments card (and close it again)."""
        if self.prs.due(now):
            self.prs.check(now)
        new = self.prs.poll()
        if new:
            kind, fields = pr_news(new)
            self.react(kind, 2.5, **fields)
            self.greet_if_free()
            self.gh_hop_until = now + 6
        gh = self.badges.get("github")
        if self.prs.unread and not gh:
            gh = self.badges["github"] = self.fx.badge(str(self.gh_icon) if self.gh_icon.exists() else None,
                                                       self.spots.github, glyph=self.fx.pull_request)
            self.screen.redraw()  # its click area
        elif not self.prs.unread and gh:
            gh.leave()
            gh = self.badges.pop("github") and None
            self.screen.redraw()
        if gh:
            gh.label, gh.waiting = len(self.prs.unread), now < self.gh_hop_until

    def _watch_endpoints(self, now):
        """Every endpoint gets a GET every 20 minutes; she speaks up when one stops answering."""
        if self.pinger.due(now):
            self.pinger.check(now)
            self.screen.redraw()  # "checking…"
        went_down = self.pinger.poll()
        if went_down is not None:
            self.screen.redraw()
            if went_down:
                self.react("endpoint_down", 2.5, title=endpoint_down(went_down))
                button = self.overlay.rect_of("button", "observe")
                if button:
                    self.fx.nudge(button)

    # -- effects that follow what she is doing

    def _follow_with_effects(self, now, dt, motion):
        screen, fx, body = self.screen, self.fx, self.body
        if self.flash_until and now >= self.flash_until:
            self.flash_until, self.overlay.flash = None, None
            screen.redraw()
        for key, p in list(screen.presses.items()):  # buttons springing back from a press
            squash = p.step(dt)
            if squash:
                self.overlay.squash[key] = squash
            else:
                del screen.presses[key]
                self.overlay.squash.pop(key, None)
            screen.redraw()
        hx, hy = self.spots.head()
        if body.poser.label() != self.pose_seen:
            self.pose_seen = body.poser.label()
            if self.pose_seen:
                fx.flash(hx + 60, hy + 40)
        cloud = self.reactions.ponder(now, card_open=lambda: self.overlay.card_top is not None)
        if cloud is not None:
            fx.ponder(hx, hy, body.thinker.side, cloud=cloud)  # without the cloud, the trail leads to the icon
        if body.dancer.active and now >= self.next_rumble:
            if self.next_rumble:
                fx.rumble(hx + random.choice((-1, 1)) * 80, hy + 60)
            self.next_rumble = now + 4.5
        elif not body.dancer.active:
            self.next_rumble = 0.0
        if motion.walking:
            x_now = hx + motion.shift[0] * max(self.layout.size) / 2
            if body.walker.active and now >= self.next_step:
                self.next_step = now + 1.0 / Walker.STEPS_PER_SEC
                fx.step(x_now, self.win.height - 20, 1 if x_now >= self.walk_x else -1)
            self.walk_x = x_now
        if self.assistant.state == "listening" and now >= self.next_pulse:
            self.next_pulse = now + 0.9
            mic = self.overlay.rect_of("mic")
            if mic:
                fx.pulse((mic[0] + mic[2]) / 2, (mic[1] + mic[3]) / 2, 18)

    # -- painting

    def _paint(self):
        screen, overlay, panel, body, deck = self.screen, self.overlay, self.panel, self.body, self.deck
        if screen.dirty or panel.dirty:  # hover/size changes affect the pill too
            mon = panel.view()
            if mon:
                data, (mx, my, mw, mh) = overlay.render_monitor(mon)
                if (mw, mh) != (self.monitor_tex.w, self.monitor_tex.h):
                    self.monitor_tex.resize(mw, mh)
                self.monitor_tex.upload(data)
                panel.pos = (mx, my)
            panel.dirty = False
        if not screen.dirty:
            return
        self.overlay_tex.upload(overlay.render(
            {name: card.payload() for name, card in deck.cards.items()}, body.talk_left(), self.expressions.active,
            self.moves_open, body.dancer.active, body.poser.label(),
            {"walk": body.walker.active, "greet": body.greeter.active, "huh": body.huh.active},
            alerts=self.alerts.items(), monitor=panel.view(), voice=self.voice.payload(),
            thinking=body.thinker.active, gh_badge=self.spots.github if "github" in self.badges else None))
        screen.dirty = False
        screen.region_dirty = True  # card size or handles may have changed
        banner = overlay.rect_of("voice_banner")
        if banner and not self.voice.shown:
            self.fx.land(banner, word=None)
        self.voice.shown = bool(banner)
        for place in screen.after_paint:
            place()
        screen.after_paint.clear()

    def _draw_layers(self, dt):
        win = self.win
        if self.panel.shape:  # under the main layer, so open cards cover the monitor panel
            self.monitor_tex.draw(*self.panel.pos, window_h=win.height)
        self.overlay_tex.draw()
        self.fx.bounds = (win.width, win.height)
        self.fx.update(dt)
        drawn = self.fx.render()
        if drawn:  # on top of everything; clicks still go through (not in the input region)
            data, (x, y, w, h) = drawn
            if (w, h) != (self.fx_tex.w, self.fx_tex.h):
                self.fx_tex.resize(w, h)
            self.fx_tex.upload(data, GL.GL_BGRA)
            self.fx_tex.draw(x, y, window_h=win.height)

    def _update_input_region(self):
        if not self.screen.region_dirty or self.layout.drag:
            return
        ui = [(x0, y0, x1 - x0, y1 - y0) for kind, _, (x0, y0, x1, y1) in self.overlay.regions if kind != "item"]
        self.win.set_input_region(self.layout.body_region(dancing=self.body.moving) + ui)
        self.screen.region_dirty = False
