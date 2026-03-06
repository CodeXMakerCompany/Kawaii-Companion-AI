# Use ROCm PyTorch base image
FROM rocm/pytorch:rocm6.2_ubuntu22.04_py3.10_pytorch_release_2.3.0

# Set ROCm environment variables
ENV ROCM_HOME=/opt/rocm
ENV PATH=$ROCM_HOME/bin:$PATH
ENV LD_LIBRARY_PATH=$ROCM_HOME/lib:$LD_LIBRARY_PATH
ENV HSA_OVERRIDE_GFX_VERSION=11.0.0

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    python3-pip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    fastapi==0.109.0 \
    uvicorn==0.27.0 \
    TTS==0.22.0

WORKDIR /app

# Auto-accept Coqui TOS for non-interactive Docker environment
ENV COQUI_TOS_AGREED=1

# Copy voice sample
COPY assets/pneuma_voice_sample.wav /app/voice_sample.wav

# Copy service code
COPY pocs/speech-service/speech_service.py /app/

# Expose port
EXPOSE 8001

# Run the service
CMD ["uvicorn", "speech_service:app", "--host", "0.0.0.0", "--port", "8001"]
