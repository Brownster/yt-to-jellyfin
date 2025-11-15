FROM python:3.13-slim as builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    gnupg \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install yt-dlp
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp \
    && chmod a+rx /usr/local/bin/yt-dlp

# Install Deno (required for yt-dlp EJS runtime support)
RUN curl -L https://github.com/denoland/deno/releases/latest/download/deno-x86_64-unknown-linux-gnu.zip -o /tmp/deno.zip \
    && unzip /tmp/deno.zip -d /usr/local/bin \
    && rm /tmp/deno.zip \
    && chmod +x /usr/local/bin/deno

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir flask gunicorn

FROM python:3.13-slim

WORKDIR /app

# Install required dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    imagemagick \
    && rm -rf /var/lib/apt/lists/*

# Add non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy yt-dlp, Deno, and Python packages from builder
COPY --from=builder /usr/local/bin/yt-dlp /usr/local/bin/yt-dlp
COPY --from=builder /usr/local/bin/deno /usr/local/bin/deno
# Copy installed Python packages from the builder stage. This path must match
# the Python version used in the base image (3.13).
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages

# Copy application code
COPY app.py .
COPY entrypoint.sh .
COPY tubarr/ tubarr/
COPY web/ web/
RUN chmod +x entrypoint.sh

# Set environment variables
ENV OUTPUT_DIR=/media \
    VIDEO_QUALITY=1080 \
    USE_H265=true \
    CRF=28 \
    YTDLP_PATH=/usr/local/bin/yt-dlp \
    COOKIES_PATH= \
    MUSIC_OUTPUT_DIR=/media/music \
    MUSIC_DEFAULT_GENRE= \
    MUSIC_DEFAULT_YEAR= \
    JELLYFIN_MUSIC_PATH=

# Create media directory and set permissions
RUN mkdir -p /media && chown -R appuser:appuser /media /app

USER appuser

VOLUME /media
VOLUME /config

ENTRYPOINT ["/app/entrypoint.sh"]
