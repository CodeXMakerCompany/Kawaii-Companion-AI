#!/usr/bin/env bash
# Build wakeup server, run it, then open the Electron assistant UI on this machine.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "Building wakeup server..."
docker compose build wakeup-server

echo "Starting wakeup server..."
docker compose up -d wakeup-server

echo "Waiting for server to be ready..."
sleep 3

echo "Launching Electron assistant UI..."
cd "$ROOT/infra/assistant-ui"
exec npm run start
