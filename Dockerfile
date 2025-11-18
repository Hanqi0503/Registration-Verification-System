FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TOKENIZERS_PARALLELISM=false \
    OMP_NUM_THREADS=1 \
    TESSDATA_PREFIX=/usr/share/tessdata

# Install system deps: tesseract, poppler, OpenCV runtime libs and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    tesseract-ocr \
    libtesseract-dev \
    tesseract-ocr-eng \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Ensure Python can import the `app` package under /app/src
# and allow gunicorn to chdir into src so module imports like `app` work.
ENV PYTHONPATH=/app/src

# Install Python deps
COPY requirements.txt /app/
RUN python -m pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code (respect .dockerignore)
COPY . /app

# Create non-root user and fix permissions
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 5050

# Use gunicorn as WSGI server; ensure src/main.py exposes `app` (app = create_app())
CMD gunicorn src.main:app --chdir /app/src --bind 0.0.0.0:${PORT:-5050} --workers 3 --worker-class gthread --threads 4 --log-level info --access-logfile - --error-logfile -