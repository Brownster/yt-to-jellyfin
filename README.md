# Tubarr
Tubarr is a Python application that downloads YouTube playlists and processes them to work perfectly with Jellyfin/Kodi media servers. It downloads videos, generates matching NFO metadata files, renames episodes according to TV show conventions, creates artwork, and optionally converts videos to H.265 for optimized playback and reduced file size.

## Features

- **Web Interface**: Modern web dashboard to manage downloads, view progress, and manage media
- **Automated Downloads**: Download entire YouTube playlists with a single command using yt-dlp
- **Incremental Updates**: Remembers downloaded videos and only grabs new items when a playlist grows
- **Playlist Update Checker**: Automatically queue jobs when your saved playlists get new videos
- **Scheduled Playlist Checks**: Enable background scanning at a configurable interval to download new videos as soon as they appear
- **Single Video Downloads**: Individual videos are not tracked in the playlist list
- **Optional Playlist Tracking**: Choose whether a playlist should be tracked for updates
- **Proper Metadata**: Generate NFO files that Jellyfin uses to display episode details
- **Episode Renumbering**: Set custom starting episode numbers for proper sequencing
- **H.265 Conversion**: Convert videos to H.265 for better compression and playback performance
- **Artwork Generation**: Auto-generate show posters, season artwork, and episode thumbnails
- **Audiobook Downloads**: Capture single audiobook sources, fetch cover art from Google Books, and convert to tagged M4B files
- **TMDb Movie Metadata**: Fetch movie details and posters from The Movie Database when an API key is provided
- **IMDb Movie Metadata**: Retrieve movie info from IMDb when enabled
- **Filename Cleaning**: Automatically replaces underscores with spaces in filenames for better readability
- **Direct Jellyfin Integration**: Optional direct copy to Jellyfin TV library and library scan trigger
- **Docker Support**: Run as a container in your arr stack or standalone
- **Environment Configuration**: Easily customize behavior with environment variables
- **Job Management**: Track download progress and manage multiple concurrent downloads
- **Configurable Concurrency**: Limit how many playlists convert at once
- **Also works with other video platforms supported by yt-dlp sych as https://www.dailymotion.com

<img width="1836" height="761" alt="image" src="https://github.com/user-attachments/assets/93efdb9c-760e-41b0-b53c-aac99edcb457" />

<img width="1794" height="859" alt="image" src="https://github.com/user-attachments/assets/c6cadc12-cc3d-4f11-b94f-c12c88ac63cf" />


## Installation

### Option 1: Python (local)

1. **Clone the repository**:
   ```
   git clone https://github.com/Brownster/yt-to-jellyfin.git
   cd yt-to-jellyfin
   ```

2. **Install dependencies**:
   ```
   pip install -r requirements.txt
   ```

3. **Install system dependencies**:
   - **yt-dlp**: Download the latest release binary from https://github.com/yt-dlp/yt-dlp/releases and make sure it is executable
   - **Deno**: Install version 2.0.0 or later from https://deno.com/ and ensure `deno` is available on your `PATH`
   - **ffmpeg**: Required for downloads, remuxing, thumbnail extraction, and music tagging
   - **ImageMagick** (`convert` and `montage` binaries): Used for poster and collage generation
   - **Optional**: `ffprobe` (ships with ffmpeg) for codec inspection during H.265 conversion

   You can quickly verify everything is on the `PATH` with:

   ```bash
   yt-dlp --version
   deno --version
   ffmpeg -version
   convert -version
   montage -version
   ```

### Option 2: Docker

1. **Clone the repository**:
   ```
   git clone https://github.com/Brownster/yt-to-jellyfin.git
   cd yt-to-jellyfin
   ```

2. **Edit docker-compose.yml** to set your desired parameters

3. **Run with Docker Compose**:
   ```
   docker-compose up -d
   ```

## Usage

### Web Interface

Tubarr includes a modern web interface to manage your downloads and media library. By default, it runs on port 8000.

**Accessing the Web Interface**:
- When running locally: http://localhost:8000
- When running in Docker: http://localhost:8000 (or your server IP)

**Features**:
- Dashboard with stats and recent activity
- Add new YouTube playlist downloads
- Track download progress and view logs
- Review past jobs in the new **History** tab
  (number retained controlled by `COMPLETED_JOBS_LIMIT`)
- Browse your media library
- Configure application settings

### Python Application

```
# Run the web interface only:
python app.py --web-only

# Download a playlist via command line:
python app.py <YouTube Playlist URL> <TV Show Name> <Season Number> <Episode Start Number> [options]
```

**Example**:
```
python app.py "https://youtube.com/playlist?list=PLtUoAptE--3xzuDjW-7nwVbinG3GyY6JW" "Off The Hook" 01 01
```

**Options**:
- `--web-only`: Start only the web interface
- `--output-dir`: Output directory (default: ./media)
- `--quality`: Video quality height (default: 1080)
- `--no-h265`: Disable H.265 conversion
- `--crf`: CRF value for H.265 conversion (default: 28)
- `--config`: Path to config file
- `--check-updates`: Check saved playlists for new videos and queue jobs

### Movie Downloads

You can also download individual YouTube videos as movies.

**CLI**

Use `curl` to call the `/movies` endpoint:

```bash
curl -X POST http://localhost:8000/movies \
  -F video_url="https://youtube.com/watch?v=VIDEO_ID" \
  -F movie_name="My Movie"
```

**Web Interface**

Open the **New Movie Download** section, enter the video or playlist URL and the
movie name, then click **Start Download**.
Movie files will be converted to H.265 if the feature is enabled, just like TV downloads.

### Music Downloads

Tubarr can ingest music videos, albums, and playlists and tag the resulting files with embedded metadata.

**Dependencies**

- ffmpeg with `libmp3lame` support is required for audio extraction and tagging.
- yt-dlp provides the raw media and JSON metadata consumed by the tagging pipeline.
- Optional: `mutagen` is bundled via `requirements.txt` to embed ID3/Vorbis tags.

**Web Interface Forms**

Open the **New Music Download** tab and choose the form that matches your workflow:

- **Single Track** – requires **Track URL**, **Track Title**, and **Artist**. Optional fields include **Album / Collection**, **Year**, **Track #**, **Disc #**, **Genres**, custom `key=value` tags, and a **Cover Art URL**.
- **Album / Playlist** – requires **Album or Playlist URL**, **Album Title**, and **Album Artist**. You can fetch track metadata directly from YouTube, provide release year, genres, cover art, toggle embedded artwork, and curate the track table before submission.
- **Playlist & Mixes** – requires **Playlist URL** and **Collection Name**. Additional options let you set the owner/curator, specify the playlist type (original, mix, radio, etc.), cap the track count, include future updates, and supply cover art.

Submitting any form triggers a POST to `/music/jobs` and enqueues a background task. Progress is visible under **Jobs → Music** and completed collections appear in the **Music** history panel.

### Managing Playlists and Updates

When you start a download job, the playlist information is saved to
`config/playlists.json` and an archive file is created in
`config/archives/`. These files record which videos have already been
downloaded so subsequent runs only grab new content.
When adding a new playlist you can disable tracking if you don't want Tubarr to
monitor it for future updates. Tracking can also be toggled or the playlist
removed later from the **Playlists** page.

If you want to start downloading from a specific video in a playlist, set the
"Playlist Start" number when creating a job. Tubarr records this index and skips
earlier videos when checking for updates.

To check all saved playlists for newly added videos you can:

- Run `python app.py --check-updates` from the command line.
- Open the **Playlists** page in the web interface and click **Check Updates**.

Any new videos found will automatically create download jobs starting
from the next episode number, keeping your library current without
re-downloading existing files.

You can also enable an automated scheduler that periodically checks all
registered playlists. When `UPDATE_CHECKER_ENABLED` (or
`update_checker.enabled` in `config.yml`) is set to `true`, Tubarr runs a
background task every `UPDATE_CHECKER_INTERVAL` minutes to look for new
videos and queue the downloads automatically. These options are
available in the **Settings** page of the web interface.

### Docker

The Docker container will automatically start the web interface on port 8000. You can access it at http://localhost:8000.

To run:
```
docker-compose up -d
```

You can configure it by editing the `docker-compose.yml` file and the `config/config.yml` file.

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| OUTPUT_DIR | Directory to store downloaded media | ./media |
| VIDEO_QUALITY | Maximum video height (720, 1080, etc.) | 1080 |
| USE_H265 | Enable H.265 conversion | true |
| CRF | Compression quality (lower = better quality, larger files) | 28 |
| CLEAN_FILENAMES | Replace underscores with spaces in filenames | true |
| YTDLP_PATH | Path to yt-dlp executable (optional) | yt-dlp |
| COOKIES_PATH | Path to cookies file (optional) | |
| WEB_ENABLED | Enable the web interface | true |
| WEB_PORT | Port for the web interface | 8000 |
| WEB_HOST | Host for the web interface (0.0.0.0 for all interfaces) | 0.0.0.0 |
| COMPLETED_JOBS_LIMIT | Number of completed jobs to keep in history | 10 |
| MAX_CONCURRENT_JOBS | Number of playlists processed simultaneously | 1 |
| MUSIC_OUTPUT_DIR | Base folder for music downloads | ./music |
| AUDIOBOOK_OUTPUT_DIR | Base folder for audiobook downloads | /mnt/storage/audiobooks |
| UPDATE_CHECKER_ENABLED | Automatically check playlists for updates | false |
| UPDATE_CHECKER_INTERVAL | Minutes between update checks | 60 |
| CONFIG_FILE | Path to configuration file | config/config.yml |
| JELLYFIN_ENABLED | Enable direct Jellyfin integration | false |
| JELLYFIN_TV_PATH | Path to Jellyfin TV library folder | |
| JELLYFIN_MOVIE_PATH | Path to Jellyfin movie library folder | |
| JELLYFIN_HOST | Jellyfin server hostname/IP | |
| JELLYFIN_PORT | Jellyfin server port | 8096 |
| JELLYFIN_API_KEY | Jellyfin API key for triggering library scan (optional) | |
| TMDB_API_KEY | TMDb API key for enhanced movie metadata (optional) | |
| IMDB_ENABLED | Enable IMDb metadata provider | false |
| IMDB_API_KEY | IMDb API key for movie metadata (optional) | |

Set `TMDB_API_KEY` or configure `tmdb.api_key` in `config.yml` to enable
automatic movie metadata and poster retrieval from The Movie Database.
Enable IMDb metadata by setting `IMDB_ENABLED` and providing `IMDB_API_KEY` or
editing the `imdb` section in `config.yml`.

If `YTDLP_PATH` is not provided, Tubarr will search common locations
(`/usr/local/bin/yt-dlp`, `/usr/bin/yt-dlp`) and fall back to simply
`yt-dlp` in the current `PATH`.

> **Note:** yt-dlp 2025.11.12 and later requires an external JavaScript runtime for
> full YouTube support. This project recommends Deno 2.0.0+ and the official
> Docker image installs it automatically.

### Using a Cookies File

Some playlists or videos require authentication in order to download them.
`yt-dlp` can use a cookies file exported from your browser to access
private or age restricted content. The file should be in the standard
`cookies.txt` format.

1. Export your browser cookies using an extension such as **Get cookies.txt**
   (Chrome) or **Cookie Quick Manager** (Firefox). Save the file as
   `cookies.txt`.
2. Set the `COOKIES_PATH` environment variable (or `cookies_path` in
   `config.yml`) to the location of this file.
3. When running in Docker, place `cookies.txt` inside the `config/`
   folder so it is available at `/config/cookies.txt` inside the
   container.

With a valid cookies file in place, `yt-dlp` will authenticate your
requests and successfully download restricted videos.

## Integrating with Jellyfin

### Method 1: Direct Integration (Recommended)

Enable the direct Jellyfin integration feature to automatically copy files to your Jellyfin library:

1. In the web interface, go to "Settings" and enable "Jellyfin integration"
2. Set the **Jellyfin TV Library Path** to the path of your Jellyfin TV library folder
3. Set the **Jellyfin Movie Library Path** (`jellyfin_movie_path` or `JELLYFIN_MOVIE_PATH`) to the path of your Jellyfin movie library folder
4. Optionally provide Jellyfin server details to trigger a library scan after copy
5. Start a new download job and files will be automatically copied to your Jellyfin library

### Method 2: Manual Integration

If you prefer to manage the files manually:

1. Make sure your videos are saved to a location Jellyfin can access
2. In Jellyfin, add a new TV Shows library pointing to your output directory
3. Set the metadata provider to "Local metadata only" to use the generated NFO files
4. Scan the library, and your shows will appear with proper metadata and artwork

### Example Folder Structure

```
media/
├── My Show
│   ├── tvshow.nfo
│   ├── poster.jpg
│   ├── fanart.jpg
│   └── Season 01
│       ├── Episode Title S01E01.mp4
│       └── Episode Title S01E01.nfo
└── My Movie (2024)
    ├── My Movie (2024) [abcd1234].mp4
    └── My Movie (2024).nfo
```

## Packaging and Installation

To build Tubarr as a Python package, install the build tool and run:

```bash
python -m pip install build
python -m build
```

This creates a wheel file in the `dist/` directory. Install it with:

```bash
pip install dist/tubarr-*.whl
```

## Testing

Tubarr includes a comprehensive test suite to verify functionality.

### Running Tests

Use the included test runner to execute tests:

```bash
# Run all tests
python run_tests.py

# Run specific test types
python run_tests.py --type basic     # Basic functionality tests
python run_tests.py --type api       # Web API endpoint tests
python run_tests.py --type job       # Job management tests
python run_tests.py --type integration # Integration tests
python run_tests.py --type web       # Web UI tests (requires webdriver)
```

### Test Structure

- `tests/test_basic.py` - Basic functionality tests
- `tests/test_api.py` - Tests for REST API endpoints
- `tests/test_job_management.py` - Tests for job management system
- `tests/test_integration.py` - Integration tests for full workflow
- `tests/web/test_frontend.py` - Web UI tests (requires Selenium webdriver)

### Linting

Install development requirements and run flake8 to check code style:

```bash
pip install -r requirements-dev.txt
flake8 .
```

### Continuous Integration

This project uses GitHub Actions for continuous integration:

- **Run Tests**: Runs the test suite on every commit and pull request
- **Docker Build**: Verifies that the Docker image builds and runs correctly when changes are made to Docker-related files

The CI workflows ensure that:
1. All tests pass on multiple Python versions
2. Tubarr builds and runs successfully in Docker
3. Dependencies are automatically kept up-to-date with Dependabot

### Automated Releases

Pushing a tag that starts with `v` (for example `v1.2.3`) automatically
creates a GitHub release. The release notes are generated from the commit
history, so simply tag your commit and push the tag:

```bash
git tag v1.2.3
git push origin v1.2.3
```

GitHub Actions will publish the release for you.

## Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the issues page.

1. Fork the repository
2. Create your feature branch: `git checkout -b feature/my-new-feature`
3. Commit your changes: `git commit -am 'Add some feature'`
4. Push to the branch: `git push origin feature/my-new-feature`
5. Open a pull request

When contributing, please ensure that new code is covered by tests.

## License

Distributed under the MIT License. See `LICENSE` for more information.

## Acknowledgements

- yt-dlp for video downloading capabilities
- ffmpeg for video processing
- ImageMagick for artwork generation
- Jellyfin/Kodi for the amazing media servers
