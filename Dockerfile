FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy only what the wakeup server needs (adapters, core, domain, events, services, utils, infra, wakeup.py)
COPY wakeup.py .
COPY adapters ./adapters
COPY core ./core
COPY domain ./domain
COPY events ./events
COPY services ./services
COPY utils ./utils
COPY infra ./infra

# So "import infra" and other app packages resolve when running python wakeup.py
ENV PYTHONPATH=/app

# Expose WebSocket port
EXPOSE 7769

# Run the wakeup server
CMD ["python", "wakeup.py"]
