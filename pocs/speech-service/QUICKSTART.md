# Quick Start Guide

## TL;DR - Get GPU Working in 3 Commands

```bash
cd pocs/speech-service
chmod +x *.sh && ./setup-gpu.sh && newgrp docker
./test-gpu.sh  # Should show your AMD GPU
./start-gpu.sh # Start the service
```

## What's Happening?

Your Docker Desktop can't directly access GPU because it runs in a VM. But your system also has native Docker running, which CAN access the GPU.

The scripts automatically switch to the native Docker socket for GPU access.

## Step-by-Step

### 1. Setup (one-time)

```bash
cd pocs/speech-service
chmod +x *.sh
./setup-gpu.sh
```

This adds you to the `docker` group. You'll need to either:

- Run `newgrp docker`, OR
- Log out and back in

### 2. Test GPU Access

```bash
./test-gpu.sh
```

You should see output like:

```
CUDA available: True
Device count: 1
Device name: AMD Radeon RX 7900 XTX
```

If you see `CUDA available: False`, the GPU isn't accessible. Check:

```bash
lsmod | grep amdgpu  # Driver loaded?
ls -la /dev/dri/     # Devices exist?
groups | grep docker # In docker group?
```

### 3. Start the Service

```bash
./start-gpu.sh
```

First run takes ~5 minutes to download the TTS model.

### 4. Test It

In another terminal:

```bash
cd pocs/speech-service
./test_service.sh
```

Or use Python:

```bash
python3 client.py
```

## Troubleshooting

### "Permission denied" on docker socket

```bash
sudo usermod -aG docker $USER
newgrp docker
```

### GPU not detected

Try CPU mode instead:

```bash
docker-compose -f docker-compose.cpu.yml up --build
```

### Service crashes on startup

Check logs:

```bash
docker-compose logs -f
```

Common issues:

- Out of memory: Close other GPU apps
- Wrong GPU arch: Edit `docker-compose.yml` PYTORCH_ROCM_ARCH

## Integration with Your Code

Once running, use the client:

```python
from pocs.speech_service.client import RemoteSpeechService

async with RemoteSpeechService() as speech:
    # Check if service is up
    health = await speech.health_check()
    print(health)

    # Generate speech
    await speech.synthesize_to_file(
        "Hello from the containerized service!",
        "output.wav"
    )
```

Replace your current `SileroSpeech.save_and_play()` calls with this client.

## Why This Approach?

- Host system stays clean (no ROCm installation)
- If container breaks, just `docker-compose down` and rebuild
- GPU acceleration when available, CPU fallback when not
- Your main.py stays async and non-blocking
