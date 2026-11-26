"""Voice commands: record with PipeWire (pw-record), transcribe locally with faster-whisper,
then run a mapped command from commands.json (apps x open/close verbs, plus exact phrases),
or ask OpenRouter (free models) for anything unknown.

AI-suggested commands are never run blind: they come back as a "confirm" event. Once the
user approves one and it runs successfully, it is saved into commands.json next to the
built-in ones, so it runs directly from then on. Destructive commands are refused.
Entries marked "confirm" in commands.json (turning the PC off) ask the same way. A confirm
can be answered by voice too: "yes"/"sí" runs it, "no"/"cancela" cancels it.

All slow work (model load, transcription, HTTP) happens on one worker thread; the UI
reads results with poll().
"""

import glob
import json
import os
import queue
import re
import signal
import subprocess
import tempfile
import threading
import time
import unicodedata
import urllib.error
import urllib.request
import wave
from pathlib import Path

import numpy as np

MAX_SECONDS = 15  # recording stops by itself after this
FREE_MODELS = [  # tried in order; the one that answers moves to the front
    "baidu/ernie-5.5-flash-preview:free",
    "cohere/north-mini-code:free",
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "inclusionai/ling-3.2-flash:free",
    "recursive/flint-v1.0:free",
]
AI_TIMEOUT, AI_BUDGET = 12, 35  # seconds per model / for the whole chain
DENY = re.compile(
    r"\bsudo\b|\bsu\b|\brm\b|\brmdir\b|\bdd\b|mkfs|\bshred\b|\bshutdown\b|\breboot\b|\bpoweroff\b|\bhalt\b|"
    r"\bkill\b|\bchmod\b|\bchown\b|\bsystemctl\b|\bpasswd\b|\buserdel\b|\bcrontab\b|"
    r">\s*/(dev|etc|boot|usr)|:\(\)\s*\{|\|\s*(ba|z)?sh\b|\bmv\s+/|\btruncate\b|\bformat\b|\beval\b"
)
HARD_SIGNAL = re.compile(r"(^|\s)-(9|KILL|SIGKILL|STOP|SIGSTOP|s\s*(9|KILL))\b|--signal")
PROTECTED = re.compile(r"cosmic|systemd|pipewire|wireplumber|xwayland|dbus|gnome-keyring|ssh|login|init\b|"
                       r"networkmanager|polkit|python|bash|\bsh\b|zsh|viewer|claude-code|node\b", re.I)


def allowed(command):
    """Policy for AI-suggested commands. Closing an app gracefully is fine (pkill/killall
    with the default SIGTERM, flatpak kill); hard signals, system processes and anything
    in DENY are not."""
    check = re.sub(r"\bflatpak\s+kill\b", "flatpak_kill", command)
    if DENY.search(check):
        return False
    if re.search(r"\b(pkill|killall)\b|flatpak_kill", check):
        target = re.sub(r"\b(pkill|killall|flatpak_kill)\b|(^|\s)-\w+", " ", check)
        return not HARD_SIGNAL.search(check) and not PROTECTED.search(target)
    return True


def normalize(text):
    """Lowercase, no accents or punctuation, single spaces: 'Abre Brave!' -> 'abre brave'."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9ñ ]+", " ", text).split())


FILLER = {"el", "la", "los", "las", "lo", "the", "a", "an", "un", "una", "please", "por", "favor", "porfa", "my", "mi",
          "app", "aplicacion", "programa"}


def core(phrase):
    """Drop articles and polite filler so 'cierra el slack por favor' matches 'cierra slack'."""
    return " ".join(w for w in phrase.split() if w not in FILLER)


YES = {"yes", "yeah", "yep", "sure", "ok", "okay", "confirm", "run", "do", "it", "go", "ahead",
       "si", "claro", "dale", "hazlo", "confirmo", "adelante", "correlo", "ejecutalo"}
NO = {"no", "nope", "nah", "cancel", "cancela", "cancelar", "mejor", "don", "t", "dont", "do", "it"}


def answer(phrase):
    """'sí por favor' -> True, 'no cancela' -> False, anything else -> None."""
    words = core(phrase).split()
    if words and "no" not in words and all(w in YES for w in words):
        return True
    if words and all(w in NO for w in words):
        return False
    return None


def desktop_ids():
    dirs = ["/usr/share/applications", os.path.expanduser("~/.local/share/applications"),
            "/var/lib/flatpak/exports/share/applications", os.path.expanduser("~/.local/share/flatpak/exports/share/applications")]
    return sorted({os.path.basename(p)[:-8] for d in dirs for p in glob.glob(d + "/*.desktop")})


class Recorder:
    """pw-record into a temporary 16 kHz mono WAV; SIGINT finishes the file cleanly."""

    def __init__(self):
        self.proc = None
        self.path = None
        self.started = 0.0

    @property
    def active(self):
        return self.proc is not None

    def start(self):
        fd, self.path = tempfile.mkstemp(prefix="shark-voice-", suffix=".wav")
        os.close(fd)
        self.proc = subprocess.Popen(["pw-record", "--rate", "16000", "--channels", "1", "--format", "s16", self.path],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.started = time.monotonic()

    def stop(self):
        if not self.proc:
            return None
        self.proc.send_signal(signal.SIGINT)
        try:
            self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.proc = None
        return self.path


def read_wav(path):
    with wave.open(path, "rb") as w:
        data = w.readframes(w.getnframes())
    return np.frombuffer(data, np.int16).astype(np.float32) / 32768.0


def openrouter(key_file, models, system, text, max_tokens=400, accept=None):
    """Ask OpenRouter's free models in turn until one gives an acceptable reply; returns
    (accepted reply, None) or (None, why not). accept(content) returns the reply to keep, or
    None to try the next model (by default: any non-empty text). The model that answered is
    moved to the front of `models`, so it is asked first next time."""
    try:
        key = Path(key_file).read_text().strip()
    except OSError:
        return None, f"No OpenRouter key in {key_file}"
    accept = accept or (lambda content: content.strip() or None)
    last_error = "AI unavailable"
    deadline = time.monotonic() + AI_BUDGET
    for model in list(models):
        remaining = deadline - time.monotonic()
        if remaining < 2:
            last_error += " (gave up: free models too slow right now)"
            break
        body = {"model": model, "temperature": 0, "max_tokens": max_tokens,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": text}]}
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions", data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                     "X-Title": "shark-viewer"})
        try:
            with urllib.request.urlopen(req, timeout=min(AI_TIMEOUT, remaining)) as resp:
                content = json.load(resp)["choices"][0]["message"].get("content") or ""
        except urllib.error.HTTPError as e:  # 429 rate limit, 5xx, ...: try the next free model
            last_error = f"{model}: HTTP {e.code}"
            continue
        except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as e:
            last_error = f"{model}: {e}"
            continue
        reply = accept(content)
        if reply is None:  # some free models answer with an empty or malformed message
            last_error = f"{model}: unusable reply"
            continue
        models.remove(model)
        models.insert(0, model)  # it works: ask it first next time
        return reply, None
    return None, last_error


class VoiceAssistant:
    """States: idle -> listening -> thinking -> (confirm) -> idle. Events from poll():
    ("status", text[, meta]), ("heard", text), ("run", command, say, meta), ("confirm", command, say, meta),
    ("learned", phrase), ("error", text, meta). meta = {"kind": ..., "app": ...} tells the UI
    which line she should say (open/close/not_open/refused/...)."""

    def __init__(self, app_dir, config_dir):
        self.commands_file = Path(app_dir) / "commands.json"
        self.legacy_cache = Path(config_dir) / "command_cache.json"  # before AI commands lived in commands.json
        self.key_file = Path(config_dir) / "openrouter_key"
        self.log_file = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "shark-viewer-commands.log"
        self.recorder = Recorder()
        self.state = "idle"
        self.pending = None  # (normalized phrase, command, say, meta) waiting for Run/Cancel or a spoken yes/no
        self.models = list(FREE_MODELS)
        self.model = None  # faster-whisper, loaded lazily on the worker
        self.jobs = queue.Queue()
        self.events = queue.Queue()
        self._commands, self._commands_mtime = {}, None
        self._migrate_cache()
        threading.Thread(target=self._worker, daemon=True, name="voice").start()

    # ---- UI side --------------------------------------------------------------
    def toggle(self):
        if self.state == "listening":
            self.stop_listening()
        elif self.state in ("idle", "confirm"):  # a pending confirm stays: the answer may be spoken
            self.recorder.start()
            self.state = "listening"
            self.jobs.put(("warm",))  # load the model while she listens
            self.events.put(("status", "Listening… click the mic or Alt+F10 to stop"))

    def stop_listening(self):
        path = self.recorder.stop()
        self.state = "thinking"
        self.events.put(("status", "Thinking…"))
        self.jobs.put(("transcribe", path))

    def tick(self):
        """Call every frame: enforces the recording time limit."""
        if self.state == "listening" and time.monotonic() - self.recorder.started > MAX_SECONDS:
            self.stop_listening()

    def confirm(self, approved):
        if not self.pending:
            return
        phrase, command, say, meta = self.pending
        self.pending, self.state = None, "idle"
        if approved:
            proc = self._run(command)
            self.events.put(("run", command, say, meta))
            if meta["kind"] == "ai":  # saved into commands.json only if it really worked
                self._check(proc, (f"That command failed, so I didn't save it: {command}", {"kind": "ai_failed"}),
                            (phrase, command, say))
            else:
                self._check(proc, (f"That didn't work: {command}", {"kind": "failed"}))
        else:
            self.events.put(("status", "Cancelled", {"kind": "cancelled"}))

    def poll(self):
        out = []
        while True:
            try:
                out.append(self.events.get_nowait())
            except queue.Empty:
                return out

    # ---- worker -----------------------------------------------------------------
    def _worker(self):
        while True:
            job = self.jobs.get()
            try:
                if job[0] == "warm":
                    self._load_model()
                elif job[0] == "transcribe":
                    self._handle(job[1])
            except Exception as e:  # never let the worker die
                self.state = "idle"
                self.events.put(("error", f"Voice error: {e}", {"kind": "error"}))

    def _load_model(self):
        if self.model is None:
            from faster_whisper import WhisperModel
            # base multilingual (English + Spanish), int8 on CPU, a third of the cores at most
            self.model = WhisperModel("base", device="cpu", compute_type="int8",
                                      cpu_threads=max(2, min(8, (os.cpu_count() or 4) // 3)))

    def _transcribe(self, path):
        self._load_model()
        audio = read_wav(path)
        if audio.size < 16000 * 0.3:
            return ""
        labels = ", ".join(a["label"] for a in self._load().get("apps", []))
        segments, _ = self.model.transcribe(  # the prompt nudges Whisper toward our app names
            audio, beam_size=1, vad_filter=True, without_timestamps=True,
            initial_prompt=f"Open or close {labels}. Abre o cierra {labels}.")
        return " ".join(s.text for s in segments).strip()

    def _handle(self, path):
        try:
            text = self._transcribe(path) if path else ""
        finally:
            if path:
                Path(path).unlink(missing_ok=True)
        phrase = normalize(text)
        if not phrase:
            self.state = "confirm" if self.pending else "idle"  # still waiting for Run/Cancel
            self.events.put(("error", "I didn't catch that", {"kind": "not_heard"}))
            return
        self.events.put(("heard", text))

        if self.pending:  # she asked "sure?": a spoken yes/no answers it, anything else drops it
            reply = answer(phrase)
            if reply is not None:
                self.confirm(reply)
                return
            self.pending = None

        hit = self._match(phrase)
        if hit and hit[3].get("confirm"):  # e.g. turning the PC off: ask first
            command, say, _, meta = hit
            self.pending = (phrase, command, say, meta)
            self.state = "confirm"
            self.events.put(("confirm", command, say, meta))
            return
        if hit:
            command, say, failure, meta = hit
            proc = self._run(command)
            self.state = "idle"
            self.events.put(("run", command, say, meta))
            self._check(proc, failure)  # e.g. "Brave isn't open" when there is nothing to close
            return

        self.events.put(("status", f"“{text}”: asking AI…"))
        command, say = self._ask_ai(text)
        if not command:
            self.state = "idle"
            down = "HTTP" in (say or "") or "gave up" in (say or "") or "unavailable" in (say or "")
            self.events.put(("error", say or "No command for that", {"kind": "ai_down" if down else "no_command"}))
        elif not allowed(command):
            self.state = "idle"
            self.events.put(("error", f"Refused (not allowed): {command}", {"kind": "refused"}))
        else:
            self.pending = (phrase, command, say or "Done", {"kind": "ai"})
            self.state = "confirm"
            self.events.put(("confirm", command, say or "", {"kind": "ai"}))

    # ---- commands ---------------------------------------------------------------
    def _load(self):
        """commands.json, re-read only when the file changes (you can edit it while she runs)."""
        try:
            mtime = self.commands_file.stat().st_mtime
            if mtime != self._commands_mtime:
                self._commands = json.loads(self.commands_file.read_text(encoding="utf-8"))
                self._commands_mtime = mtime
        except (OSError, ValueError):
            pass
        return self._commands

    def _match(self, phrase):
        """Longest matching phrase wins. Returns (command, say, (failure text, meta), meta) or None."""
        data = self._load()
        padded = f" {core(phrase)} "
        best = None
        verbs = data.get("verbs", {})
        for app in data.get("apps", []):
            label = app["label"]
            for kind, doing, failure in (("close", "Closing", (f"{label} isn't open", {"kind": "not_open", "app": label})),
                                         ("open", "Opening", (f"Couldn't open {label}", {"kind": "open_failed", "app": label}))):
                if not app.get(kind):
                    continue
                for name in app["names"]:
                    for verb in verbs.get(kind, []):
                        p = core(normalize(f"{verb} {name}"))
                        if f" {p} " in padded and (best is None or len(p) > best[0]):
                            best = (len(p), app[kind], f"{doing} {label}", failure, {"kind": kind, "app": label})
        for entry in data.get("commands", []):
            for p in (core(normalize(x)) for x in entry["phrases"]):
                if p and f" {p} " in padded and (best is None or len(p) > best[0]):
                    best = (len(p), entry["run"], entry.get("say", "Done"),
                            (f"That didn't work: {entry['run']}", {"kind": "failed"}),
                            {"kind": "phrase", "confirm": entry.get("confirm", False), "react": entry.get("react")})
        return best[1:] if best else None

    def _learn(self, phrase, command, say):
        """Save an approved, successful AI command into commands.json."""
        data = json.loads(self.commands_file.read_text(encoding="utf-8"))
        commands = data.setdefault("commands", [])
        if not any(phrase in map(normalize, c["phrases"]) for c in commands):
            commands.append({"phrases": [phrase], "run": command, "say": say, "source": "ai",
                             "added": time.strftime("%Y-%m-%d %H:%M")})
            self.commands_file.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    def _migrate_cache(self):
        """Older builds cached AI commands in the config dir: fold them into commands.json once."""
        try:
            cache = json.loads(self.legacy_cache.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        for phrase, entry in cache.items():
            self._learn(phrase, entry["run"], entry.get("say", "Done"))
        self.legacy_cache.unlink(missing_ok=True)

    def _check(self, proc, failure, learn=None):
        """Verify in the background, so a long-running launch never holds up the next command."""
        threading.Thread(target=self._verify, args=(proc, failure, learn), daemon=True).start()

    def _verify(self, proc, failure, learn=None):
        """A command that exits non-zero within 3 s failed; one still running (or exiting 0)
        worked. Failures are reported; successes are learned when `learn` is given."""
        try:
            code = proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            code = 0  # still running: a launched app
        if code != 0:
            self.events.put(("error", *failure))
        elif learn:
            self._learn(*learn)
            self.events.put(("learned", learn[0]))

    def _run(self, command):
        """Start it detached (own session) so it outlives her, output to the commands log.
        Runs from the app folder, so commands.json can name scripts like ./poweroff.sh."""
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_file, "a") as log:
            log.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] $ {command}\n")
            log.flush()
            return subprocess.Popen(command, shell=True, start_new_session=True, stdin=subprocess.DEVNULL,
                                    stdout=log, stderr=subprocess.STDOUT, cwd=self.commands_file.parent)

    def _ask_ai(self, text):
        """Ask OpenRouter's free models for one shell command; returns (command|None, say)."""
        system = (
            "You turn a spoken request (English or Spanish) into ONE Linux shell command for Pop!_OS 24.04 "
            "with the COSMIC desktop (Wayland). Reply with JSON only, no prose: "
            '{"command": "...", "say": "short confirmation"}, or {"command": null, "say": "why"} if no shell '
            "command fits. Prefer gtk-launch <desktop-id> for installed apps and xdg-open for URLs, files and "
            "folders. To close an app use pkill -o -x <process-name> (graceful, no -9) or flatpak kill <app-id>. "
            "Never use sudo, rm, dd, mkfs, shutdown, reboot, kill -9 or anything destructive. "
            "Installed desktop ids: " + ", ".join(desktop_ids()))

        def json_reply(content):
            match = re.search(r"\{.*\}", content, re.S)
            try:
                return json.loads(match.group(0)) if match else None
            except ValueError:
                return None
        answer, error = openrouter(self.key_file, self.models, system, text, accept=json_reply)
        if answer is None:
            return None, error
        command = (answer.get("command") or "").strip() or None
        return command, str(answer.get("say") or "")
