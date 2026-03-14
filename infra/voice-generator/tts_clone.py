#!/usr/bin/env python3
"""
Convert English text to audio using Coqui TTS (XTTS v2) with voice cloning
from a reference WAV (e.g. pneuma_voice_sample.wav).
Runs on AMD (ROCm) or NVIDIA (CUDA) GPU when available, otherwise CPU.
"""

import argparse
import os
import sys

# Accept Coqui CPML non-commercial terms non-interactively (Docker / CI)
os.environ.setdefault("COQUI_TOS_AGREED", "1")


def get_device():
    """Use GPU (CUDA/ROCm) if available, else CPU."""
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        return "cpu"
    except ImportError:
        return "cpu"


def main():
    parser = argparse.ArgumentParser(
        description="Convert English text to audio using Coqui TTS with a reference voice (WAV)."
    )
    parser.add_argument(
        "text",
        nargs="?",
        default=None,
        help="English text to speak (or read from stdin if omitted)",
    )
    parser.add_argument(
        "-o", "--output",
        default="output.wav",
        help="Output WAV file path (default: output.wav)",
    )
    default_speaker = os.environ.get("VOICE_SAMPLE")
    if not default_speaker:
        default_speaker = os.path.join(
            os.path.dirname(__file__), "..", "..", "assets", "pneuma_voice_sample.wav"
        )
    parser.add_argument(
        "--speaker-wav",
        default=default_speaker,
        help="Path to reference voice WAV for cloning (default: VOICE_SAMPLE or repo assets)",
    )
    parser.add_argument(
        "--language",
        default="en",
        help="Language code (default: en)",
    )
    parser.add_argument(
        "--cpu",
        action="store_true",
        help="Force CPU (skip GPU even if available)",
    )
    args = parser.parse_args()

    text = args.text
    if text is None or text.strip() == "":
        text = sys.stdin.read().strip()
    if not text:
        print("Error: No text provided (argument or stdin).", file=sys.stderr)
        sys.exit(1)

    if not os.path.isfile(args.speaker_wav):
        print(f"Error: Speaker WAV not found: {args.speaker_wav}", file=sys.stderr)
        sys.exit(1)

    device = "cpu" if args.cpu else get_device()
    print(f"Using device: {device}", file=sys.stderr)

    try:
        from TTS.api import TTS
        import torch
    except ImportError as e:
        print(f"Error: Coqui TTS not installed. Install with: pip install TTS\n{e}", file=sys.stderr)
        sys.exit(1)

    model_name = "tts_models/multilingual/multi-dataset/xtts_v2"
    print(f"Loading model: {model_name} ...", file=sys.stderr)
    tts = TTS(model_name).to(device)

    out_path = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    print(f"Synthesizing to {out_path} ...", file=sys.stderr)
    tts.tts_to_file(
        text=text,
        speaker_wav=args.speaker_wav,
        language=args.language,
        file_path=out_path,
    )
    print(f"Done: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
