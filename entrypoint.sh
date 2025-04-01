#!/bin/bash
set -e

# Check if all required args are provided
if [ "$#" -lt 4 ]; then
  echo "Usage: $0 <YouTube URL> <TV Show Name> <Season Number> <Episode Start Number>"
  echo "Example: $0 https://youtube.com/playlist?list=PLAYLIST \"My Show\" 01 01"
  exit 1
fi

# Copy cookies file from config dir if it exists
if [ -f "/config/cookies.txt" ]; then
  export COOKIES_PATH="/config/cookies.txt"
  echo "Using cookies file from /config/cookies.txt"
fi

# Execute the app with all arguments
exec python3 /app/app.py "$@"