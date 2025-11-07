FROM python:3.11-slim

# Basic env
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    # Avoid tokenizer/process parallelism spawning extra workers
    TOKENIZERS_PARALLELISM=false \
    OMP_NUM_THREADS=1 \
    TESSDATA_PREFIX=/usr/share/tessdata

# Install system packages (Tesseract + libs for Pillow/OpenCV)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and other build tools
RUN python -m pip install --upgrade pip setuptools wheel

WORKDIR /app

# Copy requirements file for dependency installation
COPY requirements.txt /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download HF models during build to avoid runtime downloads
COPY scripts/prefetch_models.py /tmp/prefetch_models.py
RUN python -m pip install --no-cache-dir huggingface_hub && \
    python /tmp/prefetch_models.py

# Copy application source
COPY . /app

# Expose Flask port (adjust if different)
EXPOSE 5050

# Default command (adjust if you use gunicorn in production)
CMD ["python", "src/main.py"]