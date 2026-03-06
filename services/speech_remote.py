"""
Drop-in replacement for SileroSpeech that uses the containerized service.
Falls back to local SileroSpeech if the service is unavailable.
"""

import aiohttp
import asyncio
import wave
import pyaudio
import audioop
from pathlib import Path
from services.speech import SileroSpeech


class RemoteSpeechService:
    """Client for containerized speech service with fallback"""

    BASE_URL = "http://localhost:8001"
    _session = None
    _service_available = None

    @classmethod
    async def prepare(cls):
        """Initialize the service (checks if remote service is available)"""
        if cls._session is None:
            cls._session = aiohttp.ClientSession()

        # Check if remote service is available
        try:
            async with cls._session.get(
                f"{cls.BASE_URL}/health", timeout=aiohttp.ClientTimeout(total=2)
            ) as resp:
                if resp.status == 200:
                    health = await resp.json()
                    cls._service_available = True
                    print(
                        f"✓ Remote speech service connected (GPU: {health.get('gpu_available', False)})"
                    )
                    return
        except Exception as e:
            print(f"⚠ Remote speech service not available: {e}")

        # Fallback to local
        cls._service_available = False
        print("⚠ Falling back to local SileroSpeech")
        await SileroSpeech.prepare()

    @classmethod
    def generate_speech(cls, message, output_path="output.wav"):
        """Generate speech from text (sync wrapper for async call)"""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(cls._generate_speech_async(message, output_path))

    @classmethod
    async def _generate_speech_async(cls, message, output_path="output.wav"):
        """Generate speech from text using remote service or fallback"""
        if not cls._service_available:
            # Use local fallback
            return SileroSpeech.generate_speech(message, output_path)

        try:
            # Ensure output is .wav
            if not output_path.endswith(".wav"):
                output_path = output_path.rsplit(".", 1)[0] + ".wav"

            print(f"Generating speech (remote): '{message[:50]}...'")

            payload = {"text": message, "output_filename": Path(output_path).name}

            async with cls._session.post(
                f"{cls.BASE_URL}/synthesize",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    raise Exception(f"Speech service error: {error}")

                audio_data = await resp.read()

                # Save to file
                with open(output_path, "wb") as f:
                    f.write(audio_data)

                return output_path

        except Exception as e:
            print(f"⚠ Remote service failed: {e}, falling back to local")
            cls._service_available = False
            return SileroSpeech.generate_speech(message, output_path)

    @classmethod
    def save_and_play(cls, message, audio_path="output.wav", audio_level_callback=None):
        """Generate and play speech with optional lip sync callback"""
        try:
            # Generate speech (will use remote or fallback)
            audio_path = cls.generate_speech(message, audio_path)

            # Play the audio file (same as original)
            with wave.open(audio_path, "rb") as wf:
                p = pyaudio.PyAudio()
                stream = p.open(
                    format=p.get_format_from_width(wf.getsampwidth()),
                    channels=wf.getnchannels(),
                    rate=wf.getframerate(),
                    output=True,
                )

                chunk = 1024
                data = wf.readframes(chunk)
                while data:
                    stream.write(data)

                    # Calculate and send audio level for lip sync
                    if audio_level_callback is not None and len(data) > 0:
                        volume = audioop.rms(data, wf.getsampwidth())
                        # Normalize volume to 0-1 range
                        normalized_volume = min(volume / 5000.0, 1.0)
                        audio_level_callback(normalized_volume)

                    data = wf.readframes(chunk)

                # Reset mouth to closed when audio finishes
                if audio_level_callback is not None:
                    audio_level_callback(0.0)

                stream.stop_stream()
                stream.close()
                p.terminate()

        except Exception as e:
            print(f"Error during speech synthesis or playback: {e}")
            import traceback

            traceback.print_exc()
            # Reset mouth on error
            if audio_level_callback is not None:
                audio_level_callback(0.0)

    @classmethod
    async def cleanup(cls):
        """Cleanup session on shutdown"""
        if cls._session:
            await cls._session.close()
            cls._session = None


# Alias for drop-in replacement
SileroSpeechRemote = RemoteSpeechService
