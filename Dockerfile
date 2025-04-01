FROM python:3.10-slim as builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install yt-dlp
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp \
    && chmod a+rx /usr/local/bin/yt-dlp

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir flask gunicorn

FROM python:3.10-slim

WORKDIR /app

# Install required dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    imagemagick \
    && rm -rf /var/lib/apt/lists/*

# Add non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy yt-dlp and Python packages from builder
COPY --from=builder /usr/local/bin/yt-dlp /usr/local/bin/yt-dlp
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages

# Copy application code
COPY app.py .
COPY entrypoint.sh .
COPY web/ web/
RUN chmod +x entrypoint.sh

# Set environment variables
ENV OUTPUT_DIR=/media \
    VIDEO_QUALITY=1080 \
    USE_H265=true \
    CRF=28 \
    YTDLP_PATH=/usr/local/bin/yt-dlp \
    COOKIES_PATH=

# Create media directory and set permissions
RUN mkdir -p /media && chown -R appuser:appuser /media /app

USER appuser

VOLUME /media
VOLUME /config

ENTRYPOINT ["/app/entrypoint.sh"]