import os
import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
import asyncio
from pathlib import Path

# Fix for PyTorch 2.6+ weights_only security change
if hasattr(torch.serialization, "add_safe_globals"):
    try:
        from TTS.tts.configs.xtts_config import XttsConfig
        from TTS.tts.configs.vits_config import VitsConfig

        torch.serialization.add_safe_globals([XttsConfig, VitsConfig])
    except:
        pass

app = FastAPI(title="Speech Service")

# Global model instance
tts_model = None
VOICE_SAMPLE = "/app/voice_sample.wav"
OUTPUT_DIR = Path("/tmp/speech_outputs")
OUTPUT_DIR.mkdir(exist_ok=True)


class SpeechRequest(BaseModel):
    text: str
    output_filename: str = "output.wav"


@app.on_event("startup")
async def load_model():
    """Load TTS model on startup"""
    global tts_model

    print("🚀 Loading XTTS v2 model...")

    # Debug GPU detection
    print(f"PyTorch version: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"CUDA device count: {torch.cuda.device_count()}")
        print(f"CUDA device name: {torch.cuda.get_device_name(0)}")
        print(f"CUDA version: {torch.version.cuda}")
        print(
            f"HIP version: {torch.version.hip if hasattr(torch.version, 'hip') else 'N/A'}"
        )

    # Detect device
    device = "cpu"
    if torch.cuda.is_available():
        device = "cuda"
        print(f"✓ GPU detected: {torch.cuda.get_device_name(0)}")
    else:
        print("⚠ No GPU detected, using CPU")
        print("  Check: /dev/dri devices mounted? ROCm environment variables set?")

    # Load model in executor to avoid blocking
    def _load():
        import os
        from TTS.api import TTS

        # Auto-accept TOS to avoid interactive prompt in Docker
        os.environ["COQUI_TOS_AGREED"] = "1"

        model = TTS("tts_models/multilingual/multi-dataset/xtts_v2", progress_bar=False)

        # Move to GPU if available
        if device == "cuda" and hasattr(model, "synthesizer"):
            if hasattr(model.synthesizer, "tts_model"):
                model.synthesizer.tts_model.to(device)
                print("✓ Model loaded on GPU")
        else:
            print("✓ Model loaded on CPU")

        return model

    loop = asyncio.get_event_loop()
    tts_model = await loop.run_in_executor(None, _load)
    print("✓ Speech service ready")


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "model_loaded": tts_model is not None,
        "gpu_available": torch.cuda.is_available(),
    }


@app.post("/synthesize")
async def synthesize_speech(request: SpeechRequest):
    """Generate speech from text"""
    if tts_model is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet")

    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    # Generate unique output path
    output_path = OUTPUT_DIR / request.output_filename

    print(f"🎤 Generating speech: '{request.text[:50]}...'")

    # Run synthesis in executor to avoid blocking
    def _synthesize():
        tts_model.tts_to_file(
            text=request.text,
            speaker_wav=VOICE_SAMPLE,
            language="en",
            file_path=str(output_path),
        )

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _synthesize)

    print(f"✓ Speech generated: {output_path}")

    # Return the audio file
    return FileResponse(
        path=output_path, media_type="audio/wav", filename=request.output_filename
    )


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Speech Service",
        "version": "1.0.0",
        "endpoints": {"health": "/health", "synthesize": "/synthesize (POST)"},
    }
