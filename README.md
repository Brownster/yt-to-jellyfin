YouTube Playlist to Kodi/Jellyfin Episodes

A Bash script that downloads an entire YouTube playlist and postprocesses each video to work seamlessly as TV show episodes in Kodi or Jellyfin. This script downloads videos, generates matching NFO metadata files, renames episodes according to your season/episode numbering scheme, and finally converts the videos to H.265 for optimized playback.
Features

    Automated Downloads:
    Download entire YouTube playlists with a single command using yt-dlp.

    Metadata Extraction:
    Extract episode titles, descriptions, and upload dates using jq from the downloaded JSON metadata.

    NFO File Generation:
    Create NFO files that Kodi and Jellyfin can use to display episode details (title, season, episode, plot, aired date, studio, and show title).

    Episode Renumbering:
    Easily set a custom starting episode number so that your episodes are correctly sequenced.

    H.265 Conversion:
    Batch convert your downloaded MP4 files to H.265 using ffmpeg for better compression and playback performance.

    Cross-Platform Compatibility:
    Handles date formatting differences between macOS and Linux.

Dependencies

Ensure you have the following installed before running the script:

    yt-dlp (Place the executable in the same folder as the script or in your PATH)
    jq
    ffmpeg

You can verify your installations by running:

command -v ./yt-dlp
command -v jq
command -v ffmpeg

Installation

    Clone the Repository:

git clone https://github.com/yourusername/yt-playlist-to-kodi.git
cd yt-playlist-to-kodi

Make the Script Executable:

    chmod +x download_playlist.sh

    (Optional) Download yt-dlp Locally:

    If you prefer to use a local copy of yt-dlp, download the latest executable from the yt-dlp releases and place it in the project directory.

Usage

Run the script with the following parameters:

./download_playlist.sh <YouTube Playlist URL> <TV Show Name> <Season Number> <Episode Start Number>

Example

To download a playlist for the TV show "Off The Hook" (Season 01 starting at episode 01), run:

./download_playlist.sh "https://youtube.com/playlist?list=PLtUoAptE--3xzuDjW-7nwVbinG3GyY6JW&si=7EQ2A9WpbbVCnMrv" "Off The Hook" 01 01

The script will:

    Download each video and corresponding metadata.
    Rename the files to follow the naming pattern:

    Off The Hook/Season 01/<video title> S01E<episode number>.<ext>

    Generate an NFO file for each episode with the metadata Kodi/Jellyfin require.
    Convert the downloaded MP4 files to H.265 (overwriting the originals) for improved compression.

Independent Conversion Command

If you've already downloaded the playlist and just want to convert the MP4 files to H.265, run the following command from your repository root:

for video in "Off The Hook/Season 01/"*S01E*.mp4; do
  temp_file="${video%.mp4}.temp.mp4"
  ffmpeg -i "$video" -c:v libx265 -preset medium -crf 28 -c:a copy "$temp_file" &&
  mv "$temp_file" "$video" ||
  { rm -f "$temp_file"; echo "Failed to convert: $video"; }
done

This command loops over all MP4 files in the Off The Hook/Season 01/ folder, converts them using ffmpeg, and replaces the originals with the H.265-encoded versions.
Customization

    Cookies Option:
    If you require browser cookies for authentication, uncomment or adjust the COOKIES_OPTION variable in the script.

    ffmpeg Settings:
    Modify the ffmpeg parameters (-preset medium -crf 28) if you need different encoding settings.

    Output Template:
    Customize the OUTPUT_TEMPLATE in the script to change the naming format of downloaded files.

Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the issues page.

    Fork the repository.
    Create your feature branch: git checkout -b feature/my-new-feature
    Commit your changes: git commit -am 'Add some feature'
    Push to the branch: git push origin feature/my-new-feature
    Open a pull request.

License

Distributed under the MIT License. See LICENSE for more information.
Acknowledgements

    yt-dlp for the awesome video downloading capabilities.
    ffmpeg for video processing.
    jq for easy JSON parsing.
    Inspiration from numerous media center integration projects.

Happy Downloading and Enjoy Your Media!
Feel free to open an issue or contact me for any questions.
