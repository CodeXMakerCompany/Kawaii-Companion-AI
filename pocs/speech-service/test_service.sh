#!/bin/bash
# Quick test script for the speech service

echo "🧪 Testing Speech Service..."

# Wait for service to be ready
echo "⏳ Waiting for service to start..."
sleep 5

# Health check
echo ""
echo "1️⃣ Health Check:"
curl -s http://localhost:8001/health | python3 -m json.tool

# Test synthesis
echo ""
echo "2️⃣ Testing Speech Synthesis:"
curl -X POST http://localhost:8001/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello, this is a test of the AMD GPU speech service.", "output_filename": "test.wav"}' \
  --output test_output.wav

if [ -f test_output.wav ]; then
  echo "✓ Audio file generated: test_output.wav"
  ls -lh test_output.wav
else
  echo "✗ Failed to generate audio"
fi

echo ""
echo "Done! Check docker logs with: docker-compose logs -f"
