# ============================================================
# Backend Dockerfile
# Screenshot/PDF extraction app (FastAPI + Tesseract + Gemini)
# ============================================================

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# ------------------------------------------------------------
# System dependencies
# ------------------------------------------------------------
# tesseract-ocr: required by pytesseract for OCR
# libglib2.0-0 / libgl1: commonly needed by Pillow/PyMuPDF's
# underlying image libraries on slim Debian images
# ------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        libglib2.0-0 \
        libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ------------------------------------------------------------
# Python dependencies (installed before copying the rest of the
# code so Docker can cache this layer between rebuilds)
# ------------------------------------------------------------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ------------------------------------------------------------
# Application code
# ------------------------------------------------------------
COPY . .

# Tell pytesseract exactly where Tesseract lives inside this
# container (matches TESSERACT_CMD in your .env / .env.example)
ENV TESSERACT_CMD=/usr/bin/tesseract

# Render (and most hosts) inject a PORT env var at runtime and
# expect the app to bind to it -- NOT a hardcoded port.
EXPOSE 8000

# IMPORTANT: replace "main:app" below with your actual entrypoint
# if your FastAPI app object isn't in a top-level main.py.
# Examples:
#   app in backend/main.py, variable "app"        -> main:app
#   app in backend/app/main.py, variable "app"     -> app.main:app
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]