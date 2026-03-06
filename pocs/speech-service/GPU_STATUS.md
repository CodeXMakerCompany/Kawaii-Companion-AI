# GPU Status Explained

## What You Saw

```
⚠ No GPU detected, using CPU
```

This means PyTorch inside the container can't see your AMD GPU yet.

## Why?

Two possible reasons:

1. **Docker permissions** - You're not in the docker group (we're fixing this)
2. **ROCm not detecting GPU** - The container needs proper ROCm setup

## The Fix I Just Applied

1. **Auto-accept Coqui TOS** - Added `COQUI_TOS_AGREED=1` so it doesn't ask interactively
2. **Better GPU detection** - Added debug logging to see what's happening
3. **ROCm environment variables** - Set `HSA_OVERRIDE_GFX_VERSION=11.0.0` for your GPU

## Try Again

```bash
# Stop the current container
docker-compose down

# Rebuild with fixes
./run.sh
```

Now watch the startup logs. You should see:

```
PyTorch version: 2.3.0+rocm6.2
CUDA available: True
CUDA device name: AMD Radeon RX 7900 XTX
✓ GPU detected: AMD Radeon RX 7900 XTX
```

## If Still No GPU

The service will work fine on CPU (just slower). To debug GPU:

```bash
# Test GPU access from container
docker run --rm \
  --device=/dev/dri:/dev/dri \
  --group-add video \
  --group-add render \
  rocm/pytorch:rocm6.2_ubuntu22.04_py3.10_pytorch_release_2.3.0 \
  python3 -c "import torch; print(f'GPU: {torch.cuda.is_available()}')"
```

If that shows `GPU: False`, then Docker can't access your GPU devices. Common fixes:

1. Make sure you ran `newgrp docker` after adding yourself to the group
2. Check `/dev/dri` exists: `ls -la /dev/dri/`
3. Try with sudo: `sudo docker-compose up --build`

## CPU Mode is Fine Too

For testing and development, CPU mode works perfectly. It's just slower (~5-10 seconds per sentence vs ~1-2 seconds on GPU).

The important part is your host system stays safe - no ROCm installation mess!
