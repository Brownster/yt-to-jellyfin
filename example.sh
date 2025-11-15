#!/bin/bash
# Example usage of the YT-to-Jellyfin application

# Local Python usage
echo "========================================="
echo "Example 1: Running with Python directly"
echo "========================================="
echo "python app.py \"https://youtube.com/playlist?list=PLtUoAptE--3xzuDjW-7nwVbinG3GyY6JW\" \"Off The Hook\" \"01\" \"01\" --output-dir ./media"
echo ""

# Docker usage
echo "========================================="
echo "Example 2: Running with Docker"
echo "========================================="
echo "# First, edit docker-compose.yml to set your playlist and show info"
echo "docker-compose up -d"
echo ""

# Docker advanced usage
echo "========================================="
echo "Example 3: Docker with custom parameters"
echo "========================================="
echo "docker run --rm -v \$PWD/media:/media \\"
echo "    -v \$PWD/config:/config \\"
echo "    -e VIDEO_QUALITY=720 \\"
echo "    -e USE_H265=true \\"
echo "    yt-to-jellyfin \\"
echo "    \"https://youtube.com/playlist?list=YOUR_PLAYLIST_ID\" \"Show Name\" \"01\" \"01\""
echo ""

echo "Note: Make sure you have all dependencies installed:"
echo "- Python 3.7+ with required packages (pip install -r requirements.txt)"
echo "- yt-dlp"
echo "- Deno 2.0.0 or newer"
echo "- ffmpeg"
echo "- ImageMagick (for convert and montage commands)"
