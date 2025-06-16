FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libnss3 \
    libgconf-2-4 \
    libfontconfig1 \
    libxcb1 \
    libxkbcommon0 \
    xvfb \
    tesseract-ocr \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium
RUN playwright install-deps chromium

# Set up Xvfb for headless browser with GUI support
ENV DISPLAY=:99

# Copy application code
COPY . .

# Create directories for data
RUN mkdir -p /app/profiles /app/data

# Default to running the API server
CMD Xvfb :99 -screen 0 1280x1024x24 -ac & \
    uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
