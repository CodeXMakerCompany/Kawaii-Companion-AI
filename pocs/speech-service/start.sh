#!/bin/bash
# Quick start script for speech service

echo "🚀 Starting Speech Service..."
echo ""

# Check if Docker Desktop is running
if docker info 2>/dev/null | grep -q "Operating System.*Docker Desktop"; then
    echo "⚠️  Docker Desktop detected"
    echo "   GPU passthrough not supported, using CPU mode"
    echo ""
    COMPOSE_FILE="docker-compose.cpu.yml"
else
    echo "✓ Native Docker detected"
    echo "  GPU passthrough enabled"
    echo ""
    COMPOSE_FILE="docker-compose.yml"
fi

echo "Using: $COMPOSE_FILE"
echo ""

# Start the service
docker-compose -f "$COMPOSE_FILE" up --build

