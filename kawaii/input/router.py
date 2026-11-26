"""Pointer and keyboard input from the window, routed to whatever owns it: the open card,
her body (routine buttons, expressions), the side controls, or dragging her around."""

import time

from kawaii.cards.base import middle
from kawaii.input.keys import BTN_LEFT, KEY_BACKSPACE, KEY_ESC, KEY_F10, KEY_R

TALK_SECONDS = 10

# UI element kinds that react to a click (pointer cursor + hover highlight).
CLICKABLE = ("button", "item", "move", "moves_toggle", "action", "cal_prev", "cal_next", "cal_day", "cal_save",
             "cal_new", "cal_delete", "cal_event", "cal_done", "cal_yearly", "alert_action", "monitor_toggle",
             "mic", "voice_run", "voice_cancel", "gh_badge", "dec_paste", "dec_run", "dec_clear", "dec_copy",
             "dec_explain", "pk_row", "pk_back", "pk_open", "pk_cancel", "set_mon", "set_done",
             "obs_add", "obs_paste", "obs_check", "obs_done", "obs_row", "obs_input", "obs_title_in",
             "rules_add", "rules_paste", "rules_copy", "rules_back", "rules_done", "rules_row")
# Clicking these just keeps keyboard focus here (no drag).
PASSIVE = ("card", "cal_card", "cal_input", "alert", "monitor_panel", "voice_banner", "pr_card", "dec_card",
           "dec_input", "pk_card", "pk_filter", "set_card", "obs_card", "rules_card", "rules_input")
ROUTINE_BUTTONS = (("button", "dance"), ("button", "pose"), ("button", "think"), ("action", "walk"),
                   ("action", "greet"), ("action", "huh"))


class Router:
    def __init__(self, app):
        self.app = app
        win = app.win
        win.on_motion, win.on_leave, win.on_button = self.on_motion, self.on_leave, self.on_button
        win.on_scroll, win.on_text, win.on_key = self.on_scroll, self.on_text, self.on_key
        win.on_surface_changed = self.on_surface_changed

    def cursor_for(self, hit):
        drag = self.app.layout.drag
        if drag:
            return {"move": "grabbing", "left": "ew_resize", "right": "ew_resize"}.get(drag["kind"], "ns_resize")
        if hit and hit[0] == "handle":
            return "ew_resize" if hit[1] in ("left", "right") else "ns_resize"
        if hit and hit[0] in CLICKABLE:
            return "pointer"
        if hit and hit[0] == "cal_input":
            return "text"
        return "default"

    # -- pointer

    def on_motion(self, x, y):
        app, overlay = self.app, self.app.overlay
        app.screen.mouse = (x, y)
        if app.layout.drag:
            app.layout.drag_to(x, y)
            return
        app.layout.look_at(x, y)
        hit = overlay.hit(x, y)
        hover = hit if hit and (hit[0] in CLICKABLE or hit[0] == "handle") else None
        if hover != overlay.hover or not overlay.show_handles:
            overlay.hover, overlay.show_handles = hover, True
            app.screen.redraw()
        app.win.set_cursor(self.cursor_for(hit))

    def on_leave(self):
        app, overlay = self.app, self.app.overlay
        if app.layout.drag:
            return
        app.layout.look_at(-1, -1)
        if overlay.hover or overlay.show_handles:
            overlay.hover, overlay.show_handles = None, False
            app.screen.redraw()

    def on_button(self, button, pressed):
        app = self.app
        x, y = app.screen.mouse
        hit = app.overlay.hit(x, y)
        if not pressed:
            if app.layout.end_drag() is not None:
                app.win.set_cursor(self.cursor_for(hit))
            return
        rect = app.overlay.rect_of(*hit) if hit else None
        left = button == BTN_LEFT
        if hit and hit[0] in ("button", "action", "move") and left:
            app.screen.press(hit)
        if app.deck.click(hit, button, rect):
            return
        if hit and hit[0] in PASSIVE:
            return
        if left and hit and self._control(hit, rect):
            return
        if left:
            kind = hit[1] if hit and hit[0] == "handle" else "move"
            app.layout.begin_drag(kind, (x, y))
            app.win.set_cursor(self.cursor_for(hit))

    def _control(self, hit, rect):
        """Left clicks on everything that is not a card. True when the hit was one."""
        app, fx = self.app, self.app.fx
        kind = hit[0]
        if kind == "alert_action":
            fx.tap(rect)
            app.alerts.handle(hit[1])
            app.screen.redraw()
        elif kind == "mic":
            app.assistant.toggle()
            app.next_pulse = 0.0
        elif kind in ("voice_run", "voice_cancel"):
            fx.impact(rect) if kind == "voice_run" else fx.poof(*middle(rect))
            app.assistant.confirm(kind == "voice_run")
        elif kind == "monitor_toggle":
            self._toggle_monitor(rect)
        elif hit in ROUTINE_BUTTONS:
            self._routine(hit, rect)
        elif hit == ("button", "talk"):
            if app.body.talker.active:
                app.body.stop_talking()
                fx.poof(rect[2] - 12, (rect[1] + rect[3]) / 2)
            else:
                app.body.talk(TALK_SECONDS)
                fx.chatter(*app.spots.head())
            app.screen.redraw()
        elif kind == "move":
            self._expression(hit[1], rect)
        elif kind == "moves_toggle":
            app.moves_open = not app.moves_open
            app.store.set("moves_open", app.moves_open)
            app.overlay.hover = None
            app.screen.redraw()
        else:
            return False
        return True

    def _toggle_monitor(self, rect):
        app = self.app
        app.panel.toggle()
        app.screen.redraw()
        if app.panel.open:  # the panel's size is known once it is painted
            app.screen.after(lambda: app.overlay.rect_of("monitor_panel") and app.fx.bubble(
                app.overlay.rect_of("monitor_panel"), app.overlay.rect_of("monitor_toggle")))
        else:
            app.fx.poof(rect[0] + 14, (rect[1] + rect[3]) / 2)

    def _routine(self, hit, rect):
        app, fx, body = self.app, self.app.fx, self.app.body
        name = hit[1]
        routine = body.by_name(name)
        body.toggle(routine)
        if name == "greet" and body.greeter.active:
            app.speaker.react("greet")
        if name == "think":
            fx.pick(rect)
            app.reactions.user_toggled_think(time.perf_counter())
            if not body.thinker.active:  # with her brows going up
                fx.later(0.15, lambda: fx.idea(*app.spots.head(), body.thinker.side))
        elif name == "huh":
            if not body.huh.active:
                fx.poof(rect[2] - 8, (rect[1] + rect[3]) / 2, size=5)
            app.reactions.user_toggled_huh()
        elif not routine.active:
            fx.poof(rect[2] - 12, (rect[1] + rect[3]) / 2)
        elif name == "dance":
            app.impact_frame(hit)
            fx.impact(rect)
        elif name == "walk":
            fx.pick(rect)
            fx.stride(app.spots.head()[0], app.win.height - 24)
        elif name == "greet":
            fx.pick(rect)
            fx.hello(*app.spots.head())
        else:  # pose: each pose then flashes as it comes up
            fx.pick(rect)

    def _expression(self, exp, rect):
        app, fx = self.app, self.app.fx
        if exp is None:  # Clear all: a puff off every move that was on
            for on in app.expressions.active:
                r = app.overlay.rect_of("move", on)
                if r:
                    fx.poof(*middle(r), size=5)
        elif exp in app.expressions.active:
            fx.poof(rect[2] - 8, (rect[1] + rect[3]) / 2, size=5)
        else:
            fx.pick(rect)
        app.toggle_expression(exp)

    def on_scroll(self, steps):
        app = self.app
        if not app.deck.scroll(steps, app.screen.under_mouse()):
            app.layout.zoom(steps)  # manual zoom around her centre; R refits

    # -- keyboard

    def on_text(self, text):
        self.app.deck.text(text)

    def on_key(self, key, pressed):
        app = self.app
        if not pressed:
            return
        if key == KEY_F10 and app.win.xkb.alt():  # voice: start / stop listening
            app.assistant.toggle()
            return
        if app.deck.key(key, app.win.xkb.ctrl()):
            return
        if key == KEY_ESC:  # the only quit key, shown in the footer
            app.win.closed = True
        elif key == KEY_BACKSPACE:
            app.toggle_expression(None)
        elif key == KEY_R:
            app.layout.request_fit(0.0)
        elif key in app.hotkeys:  # VTube Studio "ToggleExpression"
            app.toggle_expression(app.hotkeys[key])

    def on_surface_changed(self):
        self.app.screen.region_dirty = True  # a new surface starts with a full input region: resend ours
        self.app.layout.surface_changed()
