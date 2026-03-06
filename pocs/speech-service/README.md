# Speech Service POC

Containerized speech synthesis service using Coqui TTS with AMD GPU support.

## Why?

Isolates risky ROCm/AMD GPU dependencies in Docker, keeping your host system safe.

## Quick Setup (3 steps)

```bash
cd pocs/speech-service

# 1. Setup GPU access (one-time)
chmod +x *.sh
./setup-gpu.sh
newgrp docker  # or log out/in

# 2. Test GPU access
./test-gpu.sh

# 3. Start service with GPU
./start-gpu.sh
```

If step 2 shows your GPU name, you're good to go!

## How It Works

Docker Desktop can access your AMD GPU through the native Docker socket (`/var/run/docker.sock`). The scripts automatically:

1. Add you to the `docker` group for permissions
2. Use native socket instead of Desktop's VM socket
3. Pass `/dev/dri` devices into the container
4. Configure ROCm environment variables

## Architecture

```
┌─────────────┐         HTTP          ┌──────────────────┐
│  main.py    │ ───────────────────> │  Docker Container │
│  (host)     │  POST /synthesize     │  - ROCm PyTorch   │
│             │ <─────────────────── │  - Coqui TTS      │
└─────────────┘    audio/wav          │  - AMD GPU        │
                                       └──────────────────┘
```

## Endpoints

- `GET /health` - Check service status
- `POST /synthesize` - Generate speech from text
  ```json
  {
    "text": "Hello world",
    "output_filename": "output.wav"
  }
  ```

## Fallback to CPU

If GPU doesn't work:

```bash
docker-compose -f docker-compose.cpu.yml up --build
```

## Integration with main.py

Replace `SileroSpeech` calls with `RemoteSpeechService`:

```python
from pocs.speech_service.client import RemoteSpeechService

# In your async function
async with RemoteSpeechService() as speech:
    await speech.synthesize_to_file("Hello", "output.wav")
```

## Troubleshooting

1. GPU not detected in test:

   ```bash
   # Check if amdgpu driver is loaded
   lsmod | grep amdgpu

   # Check GPU devices exist
   ls -la /dev/dri/
   ```

2. Permission denied:

   ```bash
   # Make sure you're in docker group
   groups | grep docker

   # If not, run setup again
   ./setup-gpu.sh
   newgrp docker
   ```

3. Service won't start:

   ```bash
   docker-compose logs -f
   ```

4. Remove and rebuild:
   ```bash
   docker-compose down -v
   docker-compose up --build
   ```

## GPU Configuration

Your GPU arch is auto-detected, but if needed, edit `docker-compose.yml`:

```yaml
environment:
  - PYTORCH_ROCM_ARCH=gfx1100 # Your GPU arch
  - HSA_OVERRIDE_GFX_VERSION=11.0.0
```

Find your GPU arch:

```bash
rocminfo | grep gfx
```
