#!/usr/bin/env python3
"""
Minimal HTTP server: POST /speak with {"text": "..."} to synthesize, play, then delete the file.
"""

import os
import subprocess
import sys
import tempfile
import traceback

os.environ.setdefault("COQUI_TOS_AGREED", "1")

from flask import Flask, request, jsonify, Response

app = Flask(__name__)

# Minimal page: enter text, submit → audio is generated and auto-plays
PLAY_PAGE = """
<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Speak</title></head>
<body>
  <h1>Speak</h1>
  <form id="f">
    <input type="text" name="text" id="text" placeholder="Type something..." size="40" />
    <button type="submit">Speak</button>
  </form>
  <p id="msg"></p>
  <script>
    document.getElementById("f").onsubmit = async (e) => {
      e.preventDefault();
      const text = document.getElementById("text").value.trim();
      const msg = document.getElementById("msg");
      if (!text) { msg.textContent = "Enter some text."; return; }
      msg.textContent = "Generating...";
      try {
        const r = await fetch("/speak", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: text })
        });
        if (!r.ok) { msg.textContent = "Error: " + (await r.text()); return; }
        const blob = await r.blob();
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        audio.onended = () => { URL.revokeObjectURL(url); msg.textContent = "Done."; };
        audio.onerror = () => { msg.textContent = "Playback failed."; };
        audio.play();
        msg.textContent = "Playing...";
      } catch (err) {
        msg.textContent = "Error: " + err.message;
      }
    };
  </script>
</body></html>
"""

# Load model once at startup
SPEAKER_WAV = os.environ.get("VOICE_SAMPLE", "/app/assets/pneuma_voice_sample.wav")
# Set FORCE_TTS_CPU=1 to run synthesis on CPU (workaround if GPU inference crashes the process).
FORCE_TTS_CPU = os.environ.get("FORCE_TTS_CPU", "").strip() in ("1", "true", "yes")
TTS = None
DEVICE = "cpu"


def get_device():
    if FORCE_TTS_CPU:
        return "cpu"
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def device_info():
    """Return dict with device and GPU name for /status."""
    try:
        import torch
        available = torch.cuda.is_available()
        name = None
        if available:
            try:
                name = torch.cuda.get_device_name(0)
            except Exception:
                name = "GPU (name unknown)"
        return {"device": "cuda" if available else "cpu", "gpu_name": name}
    except ImportError:
        return {"device": "cpu", "gpu_name": None}


def get_tts():
    global TTS, DEVICE
    if TTS is None:
        from TTS.api import TTS
        DEVICE = get_device()
        print(f"TTS device: {DEVICE}", flush=True)
        TTS = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(DEVICE)
    return TTS


def preload_tts():
    """Load TTS model once so first /speak does not timeout (model load can take 1–2 min)."""
    try:
        get_tts()
        print("TTS model ready.", flush=True)
    except Exception as e:
        print(f"TTS preload failed: {e}", flush=True)


@app.route("/")
def index():
    return Response(PLAY_PAGE, mimetype="text/html")


@app.route("/status")
def status():
    """Check if GPU is visible and whether TTS model is loaded."""
    info = device_info()
    info["model_loaded"] = TTS is not None
    info["tts_device"] = DEVICE
    info["force_tts_cpu"] = FORCE_TTS_CPU
    return jsonify(info)


@app.route("/ready")
def ready():
    """200 when server can accept /speak (model loaded). Use for healthcheck or before calling /speak."""
    if TTS is None:
        return jsonify({"ready": False, "message": "model loading"}), 503
    return jsonify({"ready": True})


@app.route("/speak", methods=["POST"])
def speak():
    print("[speak] request received", flush=True)
    data = request.get_json(force=True, silent=True) or {}
    text = (data.get("text") or "").strip()
    dry_run = data.get("dry_run") is True
    if not text and not dry_run:
        return jsonify({"error": "missing or empty text"}), 400
    if dry_run:
        return jsonify({"dry_run": True, "message": "request path OK, TTS not called"})

    if not os.path.isfile(SPEAKER_WAV):
        return jsonify({"error": f"speaker wav not found: {SPEAKER_WAV}"}), 500

    try:
        tts = get_tts()
    except Exception as e:
        return jsonify({"error": f"tts load: {e!s}"}), 500

    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        print(f"[speak] synthesizing {len(text)} chars to {path}", flush=True)
        sys.stdout.flush()
        sys.stderr.flush()
        tts.tts_to_file(text=text, speaker_wav=SPEAKER_WAV, language="en", file_path=path)
        print("[speak] synthesis done, reading wav", flush=True)
        sys.stdout.flush()
        try:
            subprocess.run(["aplay", "-q", path], check=False)
        except FileNotFoundError:
            pass
        with open(path, "rb") as f:
            wav_bytes = f.read()
        print(f"[speak] returning {len(wav_bytes)} bytes", flush=True)
        return Response(wav_bytes, mimetype="audio/wav", headers={"Content-Disposition": "attachment; filename=speech.wav"})
    except Exception as e:
        traceback.print_exc()
        sys.stderr.flush()
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


if __name__ == "__main__":
    info = device_info()
    print(f"Speaker WAV: {SPEAKER_WAV} (exists: {os.path.isfile(SPEAKER_WAV)})", flush=True)
    print(f"PyTorch device: {info['device']}" + (f" ({info['gpu_name']})" if info.get("gpu_name") else ""), flush=True)
    # Preload model so first /speak does not timeout (load can take 1–2 min).
    preload_tts()
    app.run(host="0.0.0.0", port=5000)
