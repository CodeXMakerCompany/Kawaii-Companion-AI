# Gunicorn config for voice-server. Preloads TTS in worker so first /speak does not timeout.
import os

bind = "0.0.0.0:5000"
workers = 1
threads = 1
timeout = 300
graceful_timeout = 60
keepalive = 30
# Use shared memory for worker heartbeat (avoids disk; important in containers).
worker_tmp_dir = "/dev/shm"

def post_worker_init(worker):
    from server import preload_tts
    preload_tts()
