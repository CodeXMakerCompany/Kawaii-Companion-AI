#!/usr/bin/env bash
# Run voice-server with GPU (ROCm). Use host Docker context so /dev/kfd and /dev/dri are passed.
set -e
cd "$(dirname "$0")"
echo "Ensure Docker context is host (for GPU): docker context use host-gpu  # or default"
echo "Starting voice-server with ROCm compose..."
docker compose -f docker-compose.rocm.yml up -d voice-server --force-recreate
echo "Check GPU: curl http://localhost:5000/status"
