# Use host Docker engine for GPU without affecting Docker Desktop

You can keep **desktop-linux** as default and add a **host-gpu** context that talks to the host Docker engine (for `/dev/kfd`, ROCm, Ollama-style GPU). Switching context does not stop or change containers on the other daemon.

## 1. Install host Docker engine (if not already)

```bash
sudo apt-get update
sudo apt-get install -y docker.io
sudo usermod -aG docker $USER
# Log out and back in (or: newgrp docker)
```

## 2. Use a separate socket so Desktop is untouched

Host engine will listen on its own socket so it doesn't conflict with Docker Desktop.

Create/edit the daemon config:

```bash
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json << 'EOF'
{
  "hosts": ["unix:///var/run/docker-host.sock"]
}
EOF
```

Then make systemd use that socket for the `docker` service:

```bash
sudo mkdir -p /etc/systemd/system/docker.service.d
sudo tee /etc/systemd/system/docker.service.d/override.conf << 'EOF'
[Service]
ExecStart=
ExecStart=/usr/bin/dockerd --host=unix:///var/run/docker-host.sock
EOF
sudo systemctl daemon-reload
```

Start the host engine (only when you need GPU):

```bash
sudo systemctl start docker
# Optional: enable on boot
# sudo systemctl enable docker
```

## 3. Create the context (does not affect existing containers)

```bash
docker context create host-gpu --docker "host=unix:///var/run/docker-host.sock"
```

Check:

```bash
docker context ls
```

You should see:

- **desktop-linux** (current) → Docker Desktop
- **host-gpu** → host engine (GPU)
- **default** → unchanged

## 4. How to use

- **Normal work (current containers, no GPU):** stay on Desktop, do nothing.
  ```bash
  docker context use desktop-linux   # if not already
  ```

- **When you need GPU (Ollama, voice-generator ROCm, etc.):**
  ```bash
  docker context use host-gpu
  docker run --rm --device /dev/kfd --device /dev/dri rocm/pytorch:latest rocm-smi
  cd infra/voice-generator && docker-compose -f docker-compose.rocm.yml up --build
  ```

- **Back to Desktop:**
  ```bash
  docker context use desktop-linux
  ```

Your “actual dockers” (containers and images on Desktop) are not affected; they live on Desktop’s daemon. The host-gpu context talks to a different daemon (host engine) on a different socket.
