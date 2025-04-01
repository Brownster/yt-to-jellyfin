# YouTube to Jellyfin

A Python application that downloads YouTube playlists and processes them to work perfectly with Jellyfin/Kodi media servers. It downloads videos, generates matching NFO metadata files, renames episodes according to TV show conventions, creates artwork, and optionally converts videos to H.265 for optimized playback and reduced file size.

## Features

- **Web Interface**: Modern web dashboard to manage downloads, view progress, and manage media
- **Automated Downloads**: Download entire YouTube playlists with a single command using yt-dlp
- **Proper Metadata**: Generate NFO files that Jellyfin uses to display episode details
- **Episode Renumbering**: Set custom starting episode numbers for proper sequencing
- **H.265 Conversion**: Convert videos to H.265 for better compression and playback performance
- **Artwork Generation**: Auto-generate show posters, season artwork, and episode thumbnails
- **Filename Cleaning**: Automatically replaces underscores with spaces in filenames for better readability
- **Direct Jellyfin Integration**: Optional direct copy to Jellyfin TV library and library scan trigger
- **Docker Support**: Run as a container in your arr stack or standalone
- **Environment Configuration**: Easily customize behavior with environment variables
- **Job Management**: Track download progress and manage multiple concurrent downloads

![image](https://github.com/user-attachments/assets/ebaf7de6-0f40-42fa-93ee-eeabc10eeec4)

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
   - yt-dlp: Download from https://github.com/yt-dlp/yt-dlp/releases
   - ffmpeg
   - ImageMagick (for convert and montage commands)

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

The application includes a modern web interface to manage your downloads and media library. By default, it runs on port 8000.

**Accessing the Web Interface**:
- When running locally: http://localhost:8000
- When running in Docker: http://localhost:8000 (or your server IP)

**Features**:
- Dashboard with stats and recent activity
- Add new YouTube playlist downloads
- Track download progress and view logs
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
| YTDLP_PATH | Path to yt-dlp executable | yt-dlp |
| COOKIES_PATH | Path to cookies file (optional) | |
| WEB_ENABLED | Enable the web interface | true |
| WEB_PORT | Port for the web interface | 8000 |
| WEB_HOST | Host for the web interface (0.0.0.0 for all interfaces) | 0.0.0.0 |
| COMPLETED_JOBS_LIMIT | Number of completed jobs to keep in history | 10 |
| CONFIG_FILE | Path to configuration file | config/config.yml |
| JELLYFIN_ENABLED | Enable direct Jellyfin integration | false |
| JELLYFIN_TV_PATH | Path to Jellyfin TV library folder | |
| JELLYFIN_HOST | Jellyfin server hostname/IP | |
| JELLYFIN_PORT | Jellyfin server port | 8096 |
| JELLYFIN_API_KEY | Jellyfin API key for triggering library scan (optional) | |

## Integrating with Jellyfin

### Method 1: Direct Integration (Recommended)

Enable the direct Jellyfin integration feature to automatically copy files to your Jellyfin library:

1. In the web interface, go to "Settings" and enable "Jellyfin integration"
2. Set the "Jellyfin TV Library Path" to the path of your Jellyfin TV library folder
3. Optionally provide Jellyfin server details to trigger a library scan after copy
4. Start a new download job and files will be automatically copied to your Jellyfin library

### Method 2: Manual Integration

If you prefer to manage the files manually:

1. Make sure your videos are saved to a location Jellyfin can access
2. In Jellyfin, add a new TV Shows library pointing to your output directory
3. Set the metadata provider to "Local metadata only" to use the generated NFO files
4. Scan the library, and your shows will appear with proper metadata and artwork

## Testing

The application includes a comprehensive test suite to verify functionality.

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

### Continuous Integration

This project uses GitHub Actions for continuous integration:

- **Run Tests**: Runs the test suite on every commit and pull request
- **Docker Build**: Verifies that the Docker image builds and runs correctly when changes are made to Docker-related files

The CI workflows ensure that:
1. All tests pass on multiple Python versions
2. The application builds and runs successfully in Docker
3. Dependencies are automatically kept up-to-date with Dependabot

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
