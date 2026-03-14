# Voice generator (Coqui TTS + Pneuma voice)

Converts **English text to audio** using [Coqui TTS](https://github.com/coqui-ai/TTS) (XTTS v2) with **voice cloning** from `assets/pneuma_voice_sample.wav`.

- **Platform:** `linux/amd64`
- **Default:** CPU (works on Pop!_OS, Docker Desktop, any host). No GPU or `/dev/kfd` required.
- **AMD GPU:** `docker-compose -f docker-compose.rocm.yml up` when you have ROCm and `/dev/kfd`, `/dev/dri`.

## Quick start (Docker)

Put your voice sample (WAV) at **`assets/pneuma_voice_sample.wav`** (repo root). From this folder (`infra/voice-generator`):

```bash
docker-compose up --build
```

Output: **"hello codexmaker seems all is fine so far"** → `./output/hello.wav`.

Custom text:

```bash
docker compose run --rm voice-generator "Your text here" -o /app/output/custom.wav
```

**HTTP server (synthesize, play, delete):** run the `voice-server` service, then POST JSON with `text`:

```bash
docker compose up -d voice-server
curl -X POST http://localhost:5000/speak -H "Content-Type: application/json" -d '{"text": "Hello world"}'
```

The server generates the audio, plays it (if `aplay` is available), then deletes the file. Port 5000.

## AMD GPU (ROCm)

When you have an AMD GPU and ROCm (/dev/kfd, /dev/dri on the host). **You must use the host Docker engine** (not Docker Desktop) so the container gets the GPU devices:

1. `docker context use host-gpu` (or `default` if that points at host socket)
2. Start with the ROCm compose:

```bash
docker compose -f docker-compose.rocm.yml up -d voice-server
```

3. **Wait until the container is healthy** (TTS model loads in the worker, ~1–2 min). Then call `/speak`:

```bash
# Optional: wait for ready
curl -s http://localhost:5000/ready
# When {"ready":true}, synthesize:
curl -X POST http://localhost:5000/speak -H "Content-Type: application/json" -d '{"text": "hello"}' -o speech.wav
```

The server runs under **gunicorn** with a 5‑minute timeout and **preloads the model** at startup so the first `/speak` does not time out. Use `/status` for device/GPU info and `model_loaded`, and `/ready` for healthchecks.

## Host requirements for GPU

- AMD GPU (e.g. Sapphire) with ROCm-supported driver.
- `/dev/kfd` and `/dev/dri` present (standard with ROCm).
- Your user in `video` and `render` groups (Docker will use these via `group_add`).

The ROCm image uses **PyTorch 2.4** (torch+torchaudio from the same index). The compose sets **`HSA_OVERRIDE_GFX_VERSION=11.0.3`** and **`HSA_ENABLE_SDMA=0`** for RX 7800 XT (gfx1102) to reduce "Page not present" / segfault during inference; if it still crashes, try `11.0.0` instead of `11.0.3`, or set **`FORCE_TTS_CPU=1`** for CPU synthesis. On the **host**, updating `linux-firmware` (e.g. from kernel.org linux-firmware repo, then `update-initramfs -u -k all` and reboot) can fix ROCm memory faults; some setups also use GRUB params like `amdgpu.cwsr_enable=0`. `/status` shows `tts_device` and `force_tts_cpu`.

Same idea as [Ollama with Docker + AMD](https://github.com/ollama/ollama/blob/main/docs/amd.md): device passthrough only, nothing to configure in the app.

## Pop!_OS: GPU-only and if inference crashes

**Try GPU again:** In `docker-compose.rocm.yml` set `FORCE_TTS_CPU=0`, then:

```bash
docker compose -f docker-compose.rocm.yml up -d voice-server --force-recreate
# wait ~2 min, then:
curl -X POST http://localhost:5000/speak -H "Content-Type: application/json" -d '{"text": "hello"}' -o speech.wav
```

If you get **connection reset by peer** or empty reply, the process is still crashing during GPU inference. Try these on the **host** (Pop!_OS), in order of risk:

| Step | What to do | Risk |
|------|------------|------|
| **1. Env only** | Already in compose: `HSA_OVERRIDE_GFX_VERSION=11.0.3`, `HSA_ENABLE_SDMA=0`. Try changing to `11.0.0` if it still crashes. | None (container only). |
| **2. Kernel param** | Add `amdgpu.cwsr_enable=0` to GRUB: edit `/etc/default/grub`, in `GRUB_CMDLINE_LINUX_DEFAULT` add `amdgpu.cwsr_enable=0`, run `sudo update-grub`, reboot. | Low. Revert by removing the param and updating grub again. |
| **3. Newer firmware** | Update AMD GPU firmware: `git clone git://git.kernel.org/pub/scm/linux/kernel/git/firmware/linux-firmware.git`, `sudo cp -r linux-firmware/amdgpu/* /lib/firmware/amdgpu/`, `sudo update-initramfs -u -k all`, reboot. | Moderate. Backup `/lib/firmware/amdgpu` first; if something breaks, restore and reboot. |
| **4. ROCm upgrade** | Upgrade **host** ROCm to 6.4+ (if Pop has packages or AMD repo). Newer ROCm improves RX 7800 XT support. | Depends on how you install; prefer distro/repo. |

If GPU still crashes, set **`FORCE_TTS_CPU=1`** again for stable CPU synthesis.

**Host vs container ROCm:**  
- **Host ROCm** = on your **local machine (outside Docker)**, e.g. Pop!_OS. You see it with `cat /opt/rocm/.info/version` (yours: 6.0.2). Upgrading “host ROCm” means upgrading ROCm on the physical system (apt/AMD repo, etc.); that’s the driver and userspace the host uses to talk to the GPU.  
- **Container/Docker** = the image has its **own** ROCm and PyTorch inside the image (we use a ROCm 6.3 base + PyTorch from index). The container uses the host’s GPU devices (`/dev/kfd`, `/dev/dri`) but the container’s own ROCm libraries. So “upgrade host ROCm” = upgrade on your PC, not inside the Dockerfile.

**What do the logs mean when I use GPU?**  
You’ll see: `[speak] request received` → `[speak] synthesizing 79 chars to /tmp/...` → then **no** `[speak] synthesis done`. Right after that, the **container restarts**, so you see the startup sequence again (Speaker WAV, PyTorch device, TTS model ready, Flask running, GET /ready). So: the process **crashes during synthesis**; Docker restarts the container; the new process prints startup and healthchecks. Every POST /speak with GPU triggers this crash–restart loop. That’s why you get empty reply: the process dies before it can send the WAV.

**Why do I get "Empty reply from server" when using GPU?**  
The model **loads** on GPU successfully (so `/status` shows `tts_device: "cuda"` and `model_loaded: true`). The crash happens **during synthesis**: when the server runs `tts_to_file(...)` it executes GPU kernels (convolutions, etc.). On RX 7800 XT with the current container (ROCm 6.3 + PyTorch 2.4 from index), that inference path hits a segfault or memory fault in the ROCm/PyTorch stack, the process dies, and curl gets connection reset → empty reply. So: load on GPU works; **inference** on GPU crashes. The only reliable fix with this stack is **`FORCE_TTS_CPU=1`** (synthesis on CPU). For GPU inference you’d need a host and image with ROCm 6.4+ and matching torch/torchaudio.

## Local Python (no Docker)

```bash
pip install TTS torch
python tts_clone.py "Your English text here" -o output.wav
```

Reference WAV default: repo `assets/pneuma_voice_sample.wav`. Override with `--speaker-wav` or `VOICE_SAMPLE`.

## Troubleshooting

**"Error while fetching server API version" / "No such file or directory" (socket)**  
The CLI can’t reach a Docker daemon. Use the **Docker Compose V2** plugin so your **context** is used:

```bash
docker compose -f docker-compose.yml up --build
```

(Note: `docker compose` with a space, not `docker-compose`.) Then:

- **Docker Desktop:** run Desktop and use context `desktop-linux` (`docker context use desktop-linux`).
- **Host engine (GPU):** use context `host-gpu` and start the host daemon: `sudo systemctl start docker` (and ensure it listens on the socket your context uses, e.g. `/var/run/docker.sock` or `/var/run/docker-host.sock`).

Or set the socket explicitly for the old `docker-compose` (V1):  
`export DOCKER_HOST=unix://$HOME/.docker/desktop/docker.sock` for Desktop, or `unix:///var/run/docker.sock` for the host engine.

**"Empty reply from server" on POST /speak**  
The worker may be dying during synthesis (OOM or native crash). Check logs and try:

```bash
# In one terminal, stream logs:
docker compose -f docker-compose.rocm.yml logs -f voice-server
# In another, run the failing request; look for "[speak] synthesizing" vs "[speak] synthesis done"
curl -X POST http://localhost:5000/speak -H "Content-Type: application/json" -d '{"text": "hello again"}' -o out.wav
```

- If logs show `[speak] synthesizing` but never `synthesis done`, the process is likely killed during inference (check `dmesg | tail` for OOM killer, or try increasing `shm_size` in `docker-compose.rocm.yml`).
- To test without gunicorn (single process): stop the main server first, then run in foreground:
  `docker compose -f docker-compose.rocm.yml stop voice-server`
  `docker compose -f docker-compose.rocm.yml run --rm -p 5000:5000 --entrypoint python voice-server server.py`
  Then in another terminal: `curl -X POST http://localhost:5000/speak ...`
  Or keep the server running and use port 5001 for the debug run: `docker compose -f docker-compose.rocm.yml run --rm -p 5001:5000 --entrypoint python voice-server server.py` then `curl ... http://localhost:5001/speak ...`

## Options

- `text` – English text (or stdin).
- `-o, --output` – Output WAV path (default: `output.wav`).
- `--speaker-wav` – Reference voice WAV for cloning.
- `--language` – Language code (default: `en`).
- `--cpu` – Force CPU inside the container (no GPU).
