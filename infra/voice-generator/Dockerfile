# Voice generator: English text → audio via Coqui TTS (XTTS v2) with voice cloning.
# AMD (Sapphire Radeon) via ROCm; falls back to CPU if no GPU.
# Platform: linux/amd64

# Use one torch stack from PyTorch ROCm 6.1 index so torch+torchaudio share same ABI (mixed base+pip = undefined symbol).
# RX 7800 XT: 6.3 base + this stack can still crash during inference; stability env vars in compose may help.
ARG ROCM_TAG=rocm6.3_ubuntu22.04_py3.10_pytorch_release_2.4.0
FROM rocm/pytorch:${ROCM_TAG} AS rocm

WORKDIR /app

# Replace with matching torch+torchaudio+torchvision from one index (avoids libtorchaudio.so symbol mismatch).
ENV TORCH_INDEX=https://download.pytorch.org/whl/rocm6.1
RUN pip uninstall -y torch torchaudio torchvision 2>/dev/null || true && \
    pip install --no-cache-dir torch torchaudio torchvision --index-url ${TORCH_INDEX}

# Install without deps so we never pull torch/torchaudio/torchvision from PyPI.
COPY requirements-rocm.txt .
RUN pip install --no-cache-dir --no-deps -r requirements-rocm.txt
RUN TORCH_VER=$(pip show torch | grep -E '^Version:' | sed 's/Version: //') && \
    echo "torch==${TORCH_VER}" > /tmp/c.txt && echo "torchaudio==${TORCH_VER}" >> /tmp/c.txt && \
    (TV=$(pip show torchvision 2>/dev/null | grep -E '^Version:' | sed 's/Version: //'); echo "torchvision==${TV:-$TORCH_VER}" >> /tmp/c.txt) && \
    echo "tokenizers>=0.21,<0.22" >> /tmp/c.txt && \
    pip install --no-cache-dir -c /tmp/c.txt \
      tokenizers regex safetensors 'huggingface-hub>=0.23' filelock pyyaml requests sympy networkx jinja2 fsspec \
      einops 'coqpit-config>=0.2' anyascii librosa matplotlib 'numba>=0.58' num2words pysbd 'scipy>=1.13' \
      'gruut>=2.4' monotonic-alignment-search 'inflect>=5.6' tqdm \
      'blinker>=1.9' 'itsdangerous>=2.2' 'werkzeug>=3.1' \
      Babel dateparser gruut-ipa gruut_lang_en scikit-learn aiohttp packaging \
      trainer
RUN pip install --no-cache-dir --no-deps 'encodec>=0.1.1'
RUN pip uninstall -y coqpit 2>/dev/null || true && pip install --no-cache-dir --force-reinstall 'coqpit-config>=0.2'
# Silence "optree is installed but the version is too old" (PyTorch Dynamo C++ pytree).
RUN pip install --no-cache-dir --upgrade 'optree>=0.13.0'
COPY tts_clone.py server.py gunicorn_conf.py ./
# Mount assets (e.g. pneuma_voice_sample.wav) at /app/assets via docker-compose

ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "tts_clone.py"]
CMD ["--help"]

# ---- CPU-only build (no GPU): use this if host has no AMD GPU or ROCm ----
FROM python:3.12-slim AS cpu

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir torch torchaudio -r requirements.txt
COPY tts_clone.py server.py ./
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "tts_clone.py"]
CMD ["--help"]
