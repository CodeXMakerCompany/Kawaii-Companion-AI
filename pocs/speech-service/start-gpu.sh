#!/bin/bash
# Start speech service with GPU support using native Docker socket

echo "🎮 Starting Speech Service with AMD GPU support..."
echo ""

# Check if user is in docker group
if ! groups | grep -q docker; then
    echo "⚠️  You're not in the 'docker' group yet"
    echo ""
    echo "Adding you now (requires sudo)..."
    sudo usermod -aG docker $USER
    echo ""
    echo "✓ Added to docker group"
    echo ""
    echo "⚠️  IMPORTANT: Run this command to activate:"
    echo "   newgrp docker"
    echo ""
    echo "Then run this script again: ./start-gpu.sh"
    exit 0
fi

# Check if GPU devices exist
if [ ! -e /dev/dri/card0 ]; then
    echo "❌ GPU device /dev/dri/card0 not found"
    echo "   Falling back to CPU mode..."
    export DOCKER_HOST=unix:///var/run/docker.sock
    docker-compose -f docker-compose.cpu.yml up --build
    exit 0
fi

echo "✓ GPU devices found:"
ls -la /dev/dri/ | grep -E "card|render"
echo ""

# Use native Docker socket for GPU access
export DOCKER_HOST=unix:///var/run/docker.sock

echo "✓ Using native Docker socket for GPU passthrough"
echo ""

# Start with GPU support
docker-compose up --build
