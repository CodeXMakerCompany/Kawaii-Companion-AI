import audioop
import os
import wave
import pyaudio
import asyncio
import torch

# Fix for PyTorch 2.6+ weights_only security change
if hasattr(torch.serialization, "add_safe_globals"):
    # Allow TTS classes to be loaded
    try:
        from TTS.tts.configs.xtts_config import XttsConfig
        from TTS.tts.configs.vits_config import VitsConfig

        torch.serialization.add_safe_globals([XttsConfig, VitsConfig])
    except:
        pass

# Lazy import TTS to avoid startup errors
TTS = None
tts_model = None
VOICE_SAMPLE = "assets/pneuma_voice_sample.wav"


class SileroSpeech:
    @staticmethod
    async def prepare():
        """Download and initialize the TTS model."""
        global TTS, tts_model

        if tts_model is None:
            print("Loading XTTS v2 model... This may take a while on first run.")

            try:
                # Import TTS here to catch errors early
                from TTS.api import TTS as TTS_API

                TTS = TTS_API

                loop = asyncio.get_event_loop()

                # Load model in executor to avoid blocking
                def load_model():
                    # Try to use GPU if available (ROCm for AMD)
                    device = "cpu"
                    if torch.cuda.is_available():
                        device = "cuda"
                        print(f"✓ GPU detected: {torch.cuda.get_device_name(0)}")
                    else:
                        print("⚠ No GPU detected, using CPU (slower)")

                    model = TTS("tts_models/multilingual/multi-dataset/xtts_v2")

                    # Move model to GPU if available
                    if (
                        device == "cuda"
                        and hasattr(model, "synthesizer")
                        and hasattr(model.synthesizer, "tts_model")
                    ):
                        model.synthesizer.tts_model.to(device)
                        print(f"✓ Model loaded on GPU")
                    else:
                        print("✓ Model loaded on CPU")
                    return model

                tts_model = await loop.run_in_executor(None, load_model)
                print("✓ TTS model loaded successfully on CPU.")
                print(f"✓ Voice cloning enabled using: {VOICE_SAMPLE}")

            except ImportError as e:
                print(f"ERROR: TTS library not properly installed: {e}")
                raise
        else:
            print("TTS model already loaded.")

    @staticmethod
    def generate_speech(message, output_path="output.wav"):
        """Generate speech from text using voice cloning."""
        global tts_model

        if tts_model is None:
            raise RuntimeError("TTS model not initialized. Call prepare() first.")

        # Ensure output is .wav
        if not output_path.endswith(".wav"):
            output_path = output_path.rsplit(".", 1)[0] + ".wav"

        print(f"Generating speech: '{message[:50]}...'")

        # Generate speech with voice cloning
        tts_model.tts_to_file(
            text=message, speaker_wav=VOICE_SAMPLE, language="en", file_path=output_path
        )
        return output_path

    @staticmethod
    def save_and_play(message, audio_path="output.wav", audio_level_callback=None):
        """Generate and play speech with optional lip sync callback."""
        try:
            # Generate speech
            audio_path = SileroSpeech.generate_speech(message, audio_path)

            # Play the audio file
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
