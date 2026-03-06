"""
Simple async client for the containerized speech service.
Drop this into your main services/ folder when ready.
"""

import aiohttp
import asyncio
from pathlib import Path


class RemoteSpeechService:
    """Client for containerized speech service"""

    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def health_check(self) -> dict:
        """Check if service is healthy"""
        async with self.session.get(f"{self.base_url}/health") as resp:
            return await resp.json()

    async def synthesize(self, text: str, output_path: str = "output.wav") -> bytes:
        """
        Generate speech from text.
        Returns audio bytes.
        """
        payload = {"text": text, "output_filename": Path(output_path).name}

        async with self.session.post(
            f"{self.base_url}/synthesize", json=payload
        ) as resp:
            if resp.status != 200:
                error = await resp.text()
                raise Exception(f"Speech service error: {error}")

            return await resp.read()

    async def synthesize_to_file(self, text: str, output_path: str = "output.wav"):
        """Generate speech and save to file"""
        audio_data = await self.synthesize(text, output_path)

        with open(output_path, "wb") as f:
            f.write(audio_data)

        return output_path


# Example usage
async def example():
    async with RemoteSpeechService() as speech:
        # Check health
        health = await speech.health_check()
        print(f"Service status: {health}")

        # Generate speech
        audio_path = await speech.synthesize_to_file(
            "Hello, this is a test of the containerized speech service.",
            "test_output.wav",
        )
        print(f"Audio saved to: {audio_path}")


if __name__ == "__main__":
    asyncio.run(example())
