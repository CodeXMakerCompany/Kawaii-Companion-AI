"""Spoken replies: Kokoro-82M (voice af_heart) running locally on the CPU, played with pw-play.

- Every line is cached as a WAV (keyed by voice + text), so it is generated only once;
  the fixed personality lines in voice_lines.json are pre-rendered in the background.
- The model (~400 MB in RAM) loads on demand and is released after IDLE_UNLOAD seconds.
- Each playback publishes a loudness envelope, so her mouth follows the real audio.
"""

import gc
import hashlib
import json
import queue
import random
import subprocess
import threading
import time
import wave
from pathlib import Path

import numpy as np

IDLE_UNLOAD = 90  # seconds without speaking before the model is released
FPS = 30  # mouth envelope resolution
THREADS = 4  # onnxruntime threads: quick enough, leaves the rest of the CPU alone


class Speaker:
    def __init__(self, model_dir, cache_dir, lines_file):
        self.model_dir = Path(model_dir)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.lines = json.loads(Path(lines_file).read_text(encoding="utf-8"))
        self.voice = self.lines.get("voice", "af_heart")
        self.speed = float(self.lines.get("speed", 1.0))
        self.available = (self.model_dir / "kokoro-v1.0.onnx").exists() and (self.model_dir / "voices-v1.0.bin").exists()
        self.kokoro = None
        self.last_used = 0.0
        self.last_pick = {}  # category -> last text, to avoid saying the same line twice in a row
        self.proc = None
        self.playing = None  # (start monotonic, envelope)
        self.jobs = queue.Queue()
        self.lock = threading.Lock()
        if self.available:
            threading.Thread(target=self._worker, daemon=True, name="speech").start()

    # ---- what to say -----------------------------------------------------------
    def pick(self, category, app=None, **fields):
        """A random line for `category` (app-specific ones first), never the same twice running."""
        options = []
        if app and app in self.lines.get("apps", {}):
            options = list(self.lines["apps"][app].get(category, []))
        options += self.lines.get(category, []) if isinstance(self.lines.get(category), list) else []
        if not options:
            return None
        if len(options) > 1 and self.last_pick.get(category) in options:
            options.remove(self.last_pick[category])
        text = random.choice(options)
        self.last_pick[category] = text
        try:
            return text.format(app=app or "it", **fields)
        except (KeyError, IndexError):
            return text

    def react(self, category, app=None, **fields):
        text = self.pick(category, app, **fields)
        if text:
            self.say(text)
        return text

    def say(self, text):
        """Speak now (anything still queued to be said is dropped: the newest line wins)."""
        if not self.available:
            return
        while True:
            try:
                job = self.jobs.get_nowait()
            except queue.Empty:
                break
            if job[0] != "say":
                self.jobs.put(job)  # keep pre-render work
                break
        self.jobs.put(("say", text))

    def prerender(self):
        """Generate every fixed line (with each app name filled in) once, in the background."""
        if not self.available:
            return
        texts = set()
        apps = list(self.lines.get("apps", {}))
        for key, value in self.lines.items():
            if isinstance(value, list):
                for t in value:
                    if "{title}" in t or "{message}" in t:
                        continue
                    if "{app}" in t:
                        texts.update(t.format(app=a) for a in apps)
                    else:
                        texts.add(t)
        for app, cats in self.lines.get("apps", {}).items():
            for t in (t for lines in cats.values() for t in lines):
                texts.add(t.format(app=app))
        for t in self.lines.get("alarms", {}).values():
            texts.add(t)
        self.jobs.put(("pre", sorted(texts)))

    def stop(self):
        with self.lock:
            if self.proc and self.proc.poll() is None:
                self.proc.terminate()
            self.proc, self.playing = None, None

    def mouth(self, now):
        """Mouth opening (0..1) for monotonic time `now` while speaking, else None."""
        playing = self.playing
        if not playing:
            return None
        start, env = playing
        i = int((now - start) * FPS)
        if i >= len(env):
            self.playing = None
            return None
        return float(env[i]) if i >= 0 else 0.0

    # ---- worker ------------------------------------------------------------------
    def _worker(self):
        while True:
            try:
                job = self.jobs.get(timeout=10)
            except queue.Empty:
                if self.kokoro and time.monotonic() - self.last_used > IDLE_UNLOAD:
                    self.kokoro = None  # give the ~400 MB back
                    gc.collect()
                continue
            try:
                if job[0] == "say":
                    self._play(self._wav(job[1]))
                elif job[0] == "pre":
                    for text in job[1]:
                        if not self.jobs.empty():  # a line to say now: do that first, resume later
                            self.jobs.put(("pre", job[1]))
                            break
                        self._wav(text)
            except Exception as e:  # speech must never take her down
                print(f"speech: {e}", flush=True)

    def _cache_path(self, text):
        key = hashlib.sha1(f"{self.voice}|{self.speed}|{text}".encode()).hexdigest()[:20]
        return self.cache_dir / f"{key}.wav"

    def _wav(self, text):
        path = self._cache_path(text)
        if path.exists():
            return path
        if self.kokoro is None:
            import onnxruntime as ort
            from kokoro_onnx import Kokoro
            opts = ort.SessionOptions()
            opts.intra_op_num_threads, opts.inter_op_num_threads = THREADS, 1
            session = ort.InferenceSession(str(self.model_dir / "kokoro-v1.0.onnx"), opts,
                                           providers=["CPUExecutionProvider"])
            self.kokoro = Kokoro.from_session(session, str(self.model_dir / "voices-v1.0.bin"))
        self.last_used = time.monotonic()
        samples, rate = self.kokoro.create(text, voice=self.voice, speed=self.speed, lang="en-us")
        tmp = path.with_suffix(".tmp")
        with wave.open(str(tmp), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes((np.clip(samples, -1, 1) * 32767).astype(np.int16).tobytes())
        tmp.replace(path)  # never leave a half-written file in the cache
        return path

    @staticmethod
    def _envelope(path):
        """Loudness per 1/FPS s, shaped for a visible but natural mouth movement."""
        with wave.open(str(path), "rb") as w:
            rate = w.getframerate()
            audio = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        step = rate // FPS
        frames = len(audio) // step
        if frames == 0:
            return np.zeros(1)
        rms = np.sqrt((audio[:frames * step].reshape(frames, step) ** 2).mean(axis=1))
        peak = np.percentile(rms, 95) or 1.0
        return np.clip(rms / peak, 0, 1) ** 0.7

    def _play(self, path):
        env = self._envelope(path)
        with self.lock:
            if self.proc and self.proc.poll() is None:
                self.proc.terminate()
            self.proc = subprocess.Popen(["pw-play", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.playing = (time.monotonic() + 0.05, env)  # pw-play takes a moment to start
