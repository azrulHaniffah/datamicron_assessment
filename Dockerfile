
# --- Enhanced Dockerfile for Gradio App ---

# Use official Python image as base
FROM python:3.11-slim

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app


# Install system dependencies (for faiss, cryptography, LLMs, and browser crawling)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libgl1 \
        libssl-dev \
        libffi-dev \
        curl \
        git \
        libstdc++6 \
        libgomp1 \
        chromium \
        chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables for Chromium (for headless crawling)
ENV CHROME_BIN=/usr/bin/chromium \
    CHROMEDRIVER_BIN=/usr/bin/chromium-driver

# Install Python dependencies first for better caching
COPY requirements.txt ./
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy only necessary project files (add .dockerignore for efficiency)
COPY . .

# Create a non-root user and switch to it for security
RUN useradd -m appuser && chown -R appuser /app
USER appuser


# Expose port 8080 for Cloud Run
EXPOSE 8080

# Set Gradio to listen on 0.0.0.0:8080 (Cloud Run requirement)
ENV GRADIO_SERVER_NAME=0.0.0.0 \
        GRADIO_SERVER_PORT=8080

# Start the Gradio app
CMD ["python", "app.py"]

# --- End of Dockerfile ---
