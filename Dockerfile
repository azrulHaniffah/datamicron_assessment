
# --- Enhanced Dockerfile for Gradio App ---

# Use official Python image as base
FROM python:3.11-slim


ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

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


ENV CHROME_BIN=/usr/bin/chromium \
    CHROMEDRIVER_BIN=/usr/bin/chromium-driver


COPY requirements.txt ./
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


COPY . .


RUN useradd -m appuser && chown -R appuser /app
USER appuser


EXPOSE 8080


ENV GRADIO_SERVER_NAME=0.0.0.0 \
        GRADIO_SERVER_PORT=8080


CMD ["python", "app.py"]
