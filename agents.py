"""Which coding-agent apps are open (Kiro, Claude), and what are their agents doing?

Each watcher answers poll(now) -> (open, state), state being IDLE, WORKING or WAITING (the
agent is stopped on you: a permission to grant, a question to answer). It looks at most
once a second: /proc for the app's process, then only what was appended to the app's logs
since its last look. A working run whose log goes quiet for minutes counts as over, and a
closed app is never anything.

Kiro logs every agent run to its "Kiro Logs" output channel, one file per window, under
~/.config/Kiro/logs/<launch>/window<N>/exthost/kiro.kiroAgent/:

    [ACPEventAdapter] Execution began {...}           a run starts
    [ACPEventAdapter] Execution yielded / resumed     between tool calls: still running
    [ACPEventAdapter] Execution succeeded {...}       the run is over (any other word ends it too)
    [PermTrace]... agent.pendingInteraction {...}     it asks you to approve a tool call
    [PermTrace]... ui.resolve {...}                   you answered

Claude Code (the CLI, and the Claude desktop app's Code tab) appends every message of a
session to ~/.claude/projects/<project>/<session>.jsonl. A prompt, a tool call or a tool
result means the agent is at it; a turn that ended means it is done; it waits on you
while a question (AskUserQuestion) or a plan (ExitPlanMode) is open, and when its turn
ended by asking you something (the desktop app's closing question, or a last line ending
in "?"). Permission prompts are not written to the transcript, so those are not seen.
"""

import glob
import json
import os
import re
import time
from pathlib import Path

IDLE, WORKING, WAITING = "idle", "working", "waiting"
CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
RECENT = 600  # log files untouched for longer are not followed (unless waiting on you)
WAIT_LIMIT = 3600  # a question unanswered for an hour is forgotten
FIRST_READ = 512 * 1024  # bytes read back from the end of a log seen for the first time


class AgentWatcher:
    """The shared part: the app's process, and following the end of its log files."""

    name = ""
    processes = ()  # /proc/<pid>/comm of the app's processes
    icons = ()  # icon files of the installed app; the first that exists is used
    logs = ""  # glob of the log files to follow
    stale = 180  # seconds of a quiet log before a working run counts as over
    side = 1  # where its icon floats beside her head: 1 right, -1 left

    def __init__(self, interval=1.0):
        self.interval = interval
        self.next_check = 0.0
        self.open, self.state = False, IDLE
        self.files = {}  # path -> {"offset": bytes read so far, "state": ..., plus parser notes}
        self.pid = None
        self.next_scan = 0.0  # when to look through /proc again while the app is closed
        self.icon = next((p for p in self.icons if os.path.exists(p)), None)

    def poll(self, now):
        """Look again when due; returns (the app is open, IDLE / WORKING / WAITING)."""
        if now < self.next_check:
            return self.open, self.state
        self.next_check = now + self.interval
        self.open = self._running(now)
        if not self.open:
            self.files.clear()
            self.state = IDLE
            return False, IDLE
        wall, states = time.time(), set()
        for path in glob.glob(self.logs):
            try:
                st = os.stat(path)
            except OSError:
                continue
            log = self.files.get(path)
            age = wall - st.st_mtime
            if age > (WAIT_LIMIT if log and log["state"] == WAITING else RECENT):
                self.files.pop(path, None)
                continue
            if log is None or st.st_size < log["offset"]:  # new to us, or rotated
                log = self.files[path] = {"offset": max(0, st.st_size - FIRST_READ), "state": IDLE}
            if st.st_size > log["offset"]:
                try:
                    with open(path, "rb") as f:
                        f.seek(log["offset"])
                        data = f.read(st.st_size - log["offset"])
                except OSError:
                    continue
                data = data[:data.rfind(b"\n") + 1]  # whole lines only; the rest next time
                log["offset"] += len(data)
                self.feed(data, log)
            if log["state"] == WAITING or (log["state"] == WORKING and age < self.stale):
                states.add(log["state"])
        self.state = WAITING if WAITING in states else WORKING if WORKING in states else IDLE
        return True, self.state

    def feed(self, data, log):
        """Read newly appended lines (oldest first) into log["state"]."""
        raise NotImplementedError

    def _running(self, now):
        if self.pid and self._is_app(self.pid):
            return True
        self.pid = None
        if now < self.next_scan:
            return False
        self.next_scan = now + 3.0  # closed: no need to read all of /proc every second
        self.pid = next((int(p) for p in os.listdir("/proc") if p.isdigit() and self._is_app(p)), None)
        return self.pid is not None

    def _is_app(self, pid):
        try:
            with open(f"/proc/{pid}/comm", "rb") as f:
                return f.read().strip() in self.processes
        except OSError:
            return False


class Kiro(AgentWatcher):
    name = "kiro"
    processes = (b"kiro",)
    icons = ("/usr/share/kiro/resources/app/resources/linux/code.png",
             "/usr/share/kiro/resources/app/extensions/kiro.kiro-agent/extension-resources/kiro-icon.png")
    logs = str(CONFIG / "Kiro" / "logs" / "*" / "window*" / "exthost" / "kiro.kiroAgent" / "Kiro Logs.log")
    side = 1
    EVENT = re.compile(rb"\[ACPEventAdapter\] Execution (\w+)|agent\.(pendingInteraction)|(ui\.resolve)\b"
                       rb"|(interactionResolved)")
    RUNNING = {b"began", b"yielded", b"resumed"}

    def feed(self, data, log):
        for run, ask, answered, resolved in self.EVENT.findall(data):
            if run:
                running = run in self.RUNNING
                if not running:
                    log["state"] = IDLE
                elif log["state"] != WAITING:
                    log["state"] = WORKING
            elif ask:
                log["state"] = WAITING
            elif (answered or resolved) and log["state"] == WAITING:
                log["state"] = WORKING


class Claude(AgentWatcher):
    name = "claude"
    processes = (b"claude-desktop", b"claude")  # the desktop app, or Claude Code in a terminal
    icons = ("/usr/share/icons/hicolor/256x256/apps/claude-desktop.png", "/usr/lib/claude-desktop/resources/icon.png")
    logs = str(Path.home() / ".claude" / "projects" / "*" / "*.jsonl")
    stale = 300  # a long build or test run writes nothing until it finishes
    side = -1
    DONE = {"end_turn", "stop_sequence", "max_tokens", "refusal"}
    ASKING = {"AskUserQuestion", "ExitPlanMode"}  # tools that wait for your answer

    def feed(self, data, log):
        for line in data.splitlines():
            # Cheap test first: big tool results are not worth parsing. Inside a message these
            # strings would be escaped (\"type\"), so a match is the record's own type.
            if not any(k in line for k in (b'"type":"assistant"', b'"type":"user"', b'"type":"system"')):
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            kind, msg = rec.get("type"), rec.get("message") or {}
            content = msg.get("content")
            blocks = [c for c in content if isinstance(c, dict)] if isinstance(content, list) else []
            if kind == "assistant":
                for b in blocks:
                    if b.get("type") == "tool_use":
                        if b.get("name") in self.ASKING:
                            log["asking"] = True
                        elif b.get("name", "").endswith("wrap_up") and (b.get("input") or {}).get("ask"):
                            log["asked"] = True  # the desktop app's closing question
                        elif b.get("name", "").endswith("AskUserQuestion"):
                            log["asking"] = True
                text = " ".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()
                if text:
                    log["question"] = text.splitlines()[-1].rstrip().endswith("?")
                if msg.get("stop_reason") in self.DONE:
                    log["state"] = WAITING if log.get("asked") or log.get("question") else IDLE
                else:
                    log["state"] = WAITING if log.get("asking") else WORKING
            elif kind == "user" and not rec.get("isMeta"):
                if any(b.get("type") == "tool_result" for b in blocks):
                    log["asking"] = False  # answered (or the tool ran): back to work
                    log["state"] = WORKING
                    continue
                text = content if isinstance(content, str) else " ".join(b.get("text", "") for b in blocks)
                log["asked"] = log["question"] = log["asking"] = False
                log["state"] = IDLE if text.startswith("[Request interrupted") else WORKING  # Esc stops it
            elif kind == "system" and rec.get("subtype") in ("stop_hook_summary", "turn_duration"):
                if log["state"] == WORKING:
                    log["state"] = IDLE  # the turn is over


WATCHERS = (Kiro, Claude)
