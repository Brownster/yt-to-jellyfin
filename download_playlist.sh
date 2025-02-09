#!/bin/bash
# This script downloads a YouTube playlist and processes each video to be compatible with Kodi/Jellyfin.
# Dependencies: jq, yt-dlp, ffmpeg

# --- Check Dependencies ---
YTDLP_CMD="./yt-dlp"  # Local yt-dlp executable
for cmd in jq ffmpeg "$YTDLP_CMD"; do
  if ! command -v "$cmd" &> /dev/null; then
    echo "Error: $cmd is required but not installed."
    exit 1
  fi
done

# --- Parameter Checking ---
if [ "$#" -ne 4 ]; then
  echo "Usage: $0 <YouTube URL> <TV Show Name> <Season Number (e.g., 01)> <Episode Start Number (e.g., 01)>"
  exit 1
fi

# Assign parameters
PLAYLIST_URL="$1"
TV_SHOW="$2"
SEASON_NUM="$3"
EPISODE_START="$4"
EPISODE_START_INT=$((10#$EPISODE_START))

# --- Folder Setup ---
FOLDER="${TV_SHOW}/Season ${SEASON_NUM}"
mkdir -p "$FOLDER"

# --- yt-dlp Configuration ---
COOKIES_OPTION="--cookies-from-browser firefox"  # Uncomment if needed
OUTPUT_TEMPLATE="${FOLDER}/%(title)s S${SEASON_NUM}E%(playlist_index)02d.%(ext)s"
LOG_FILE="yt-download.log"

# --- Download Playlist ---
echo "Starting download..." | tee -a "$LOG_FILE"
download_cmd=(
  "$YTDLP_CMD"
  $COOKIES_OPTION
  --ignore-errors
  --no-warnings
  -f 'bestvideo[height<=1080]+bestaudio/best[height<=1080]'
  -o "$OUTPUT_TEMPLATE"
  --write-info-json
  --restrict-filenames
  "$PLAYLIST_URL"
)

echo "Running: ${download_cmd[@]}" | tee -a "$LOG_FILE"
"${download_cmd[@]}" 2>&1 | tee -a "$LOG_FILE"

# --- Postprocessing ---
echo "Postprocessing files..." | tee -a "$LOG_FILE"

for JSON_FILE in "$FOLDER"/*.info.json; do
  if [ -f "$JSON_FILE" ]; then
    # Extract metadata
    TITLE=$(jq -r '.title' "$JSON_FILE")
    DESCRIPTION=$(jq -r '.description' "$JSON_FILE" | head -n 1)
    UPLOAD_DATE=$(jq -r '.upload_date' "$JSON_FILE")
    ORIGINAL_EP=$(jq -r '.playlist_index' "$JSON_FILE")

    # Handle date formatting for macOS/Linux
    if [[ "$(uname)" == "Darwin" ]]; then
      AIR_DATE=$(date -j -f "%Y%m%d" "$UPLOAD_DATE" "+%Y-%m-%d")
    else
      AIR_DATE=$(date -d "$UPLOAD_DATE" +%Y-%m-%d)
    fi

    # Calculate new episode number
    NEW_EP=$((ORIGINAL_EP - 1 + EPISODE_START_INT))
    NEW_EP_PADDED=$(printf "%02d" "$NEW_EP")

    # Rename files
    BASEFILE="${JSON_FILE%.info.json}"
    NEW_BASE=$(echo "$BASEFILE" | sed -E "s/(S${SEASON_NUM}E)[0-9]+/\1${NEW_EP_PADDED}/")

    for FILE in "${BASEFILE}".*; do
      [[ "$FILE" == *.info.json ]] && continue
      EXT="${FILE##*.}"
      NEW_FILE="${NEW_BASE}.${EXT}"
      if [[ "$FILE" != "$NEW_FILE" ]]; then
        mv "$FILE" "$NEW_FILE" || echo "Failed to rename $FILE" | tee -a "$LOG_FILE"
        echo "Renamed: $FILE → $NEW_FILE" | tee -a "$LOG_FILE"
      fi
    done

    # Generate NFO
    NFO_FILE="${NEW_BASE}.nfo"
    cat <<EOF > "$NFO_FILE"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<episodedetails>
  <title>${TITLE}</title>
  <season>${SEASON_NUM}</season>
  <episode>${NEW_EP_PADDED}</episode>
  <plot>${DESCRIPTION}</plot>
  <aired>${AIR_DATE}</aired>
  <studio>YouTube</studio>
  <showtitle>${TV_SHOW}</showtitle>
</episodedetails>
EOF
    echo "Generated NFO: $NFO_FILE" | tee -a "$LOG_FILE"
  fi
done

# Cleanup JSON files
rm -f "$FOLDER"/*.info.json

# --- Convert to H.265 ---
echo "Converting files to H.265..." | tee -a "$LOG_FILE"

for video in "$FOLDER"/*S${SEASON_NUM}E*.mp4; do
  if [ -f "$video" ]; then
    temp_file="${video%.mp4}.temp.mp4"
    ffmpeg -i "$video" -c:v libx265 -preset medium -crf 28 -c:a copy "$temp_file" 2>&1 | tee -a "$LOG_FILE"
    
    if [ $? -eq 0 ]; then
      mv "$temp_file" "$video"
      echo "Converted: $video" | tee -a "$LOG_FILE"
    else
      rm -f "$temp_file"
      echo "Failed to convert: $video" | tee -a "$LOG_FILE"
    fi
  fi
done

echo "Process completed!" | tee -a "$LOG_FILE"
