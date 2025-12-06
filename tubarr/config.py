import os
import logging
import os
from typing import Dict, Optional

import yaml
from pydantic import BaseModel, Field, ValidationError, validator

# Configure root logger if not already set
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

logger = logging.getLogger("yt-to-jellyfin")
logger.setLevel(logging.INFO)


class ConfigModel(BaseModel):
    output_dir: str = Field(..., min_length=1)
    quality: int = Field(..., gt=0)
    use_h265: bool = True
    crf: int = Field(..., ge=0, le=51)
    ytdlp_path: str = Field(..., min_length=1)
    cookies: str = ""
    completed_jobs_limit: int = Field(..., ge=1)
    max_concurrent_jobs: int = Field(1, ge=1)
    web_enabled: bool = True
    web_port: int = Field(..., ge=1, le=65535)
    web_host: str = Field(..., min_length=1)
    update_checker_enabled: bool = False
    update_checker_interval: int = Field(..., ge=1)
    jellyfin_enabled: bool = False
    jellyfin_tv_path: str = ""
    jellyfin_movie_path: str = ""
    jellyfin_music_path: str = ""
    jellyfin_host: str = ""
    jellyfin_port: int = Field(8096, ge=1, le=65535)
    jellyfin_api_key: str = ""
    tmdb_api_key: str = ""
    tvdb_api_key: str = ""
    tvdb_pin: str = ""
    imdb_enabled: bool = False
    imdb_api_key: str = ""
    clean_filenames: bool = True
    defaults: Optional[Dict[str, str]] = Field(default_factory=dict)
    music_output_dir: str = Field(..., min_length=1)
    music_default_genre: str = ""
    music_default_year: Optional[int] = Field(default=None, ge=0)
    audiobook_output_dir: str = Field(..., min_length=1)
    sonarr_blackhole_path: str = ""
    radarr_blackhole_path: str = ""

    @validator("jellyfin_tv_path", always=True)
    def validate_jellyfin_tv_path(cls, v, values):
        if values.get("jellyfin_enabled") and not v:
            raise ValueError(
                "jellyfin_tv_path is required when Jellyfin integration is enabled"
            )
        return v


def _load_config() -> Dict:
    """Load configuration from environment variables or config file."""
    # Check for a local yt-dlp in the same directory as this file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    local_ytdlp = os.path.join(script_dir, "yt-dlp")
    if os.path.exists(local_ytdlp) and os.access(local_ytdlp, os.X_OK):
        ytdlp_default = local_ytdlp
    else:
        for path in ["/usr/local/bin/yt-dlp", "/usr/bin/yt-dlp"]:
            if os.path.exists(path) and os.access(path, os.X_OK):
                ytdlp_default = path
                break
        else:
            ytdlp_default = "yt-dlp"

    config = {
        "output_dir": os.environ.get("OUTPUT_DIR", "./media"),
        "quality": os.environ.get("VIDEO_QUALITY", "1080"),
        "use_h265": os.environ.get("USE_H265", "true").lower() == "true",
        "crf": int(os.environ.get("CRF", "28")),
        "ytdlp_path": os.environ.get("YTDLP_PATH", ytdlp_default),
        "cookies": "",
        "completed_jobs_limit": int(os.environ.get("COMPLETED_JOBS_LIMIT", "10")),
        "max_concurrent_jobs": int(os.environ.get("MAX_CONCURRENT_JOBS", "1")),
        "web_enabled": os.environ.get("WEB_ENABLED", "true").lower() == "true",
        "web_port": int(os.environ.get("WEB_PORT", "8000")),
        "web_host": os.environ.get("WEB_HOST", "0.0.0.0"),
        "update_checker_enabled": os.environ.get(
            "UPDATE_CHECKER_ENABLED", "false"
        ).lower()
        == "true",
        "update_checker_interval": int(os.environ.get("UPDATE_CHECKER_INTERVAL", "60")),
        "jellyfin_enabled": os.environ.get("JELLYFIN_ENABLED", "false").lower()
        == "true",
        "jellyfin_tv_path": os.environ.get("JELLYFIN_TV_PATH", ""),
        "jellyfin_movie_path": os.environ.get("JELLYFIN_MOVIE_PATH", ""),
        "jellyfin_host": os.environ.get("JELLYFIN_HOST", ""),
        "jellyfin_port": os.environ.get("JELLYFIN_PORT", "8096"),
        "jellyfin_api_key": os.environ.get("JELLYFIN_API_KEY", ""),
        "tmdb_api_key": os.environ.get("TMDB_API_KEY", ""),
        "imdb_enabled": os.environ.get("IMDB_ENABLED", "false").lower()
        == "true",
        "imdb_api_key": os.environ.get("IMDB_API_KEY", ""),
        "tvdb_api_key": os.environ.get("TVDB_API_KEY", ""),
        "tvdb_pin": os.environ.get("TVDB_PIN", ""),
        "clean_filenames": os.environ.get("CLEAN_FILENAMES", "true").lower() == "true",
        "music_output_dir": os.environ.get("MUSIC_OUTPUT_DIR", "./music"),
        "audiobook_output_dir": os.environ.get(
            "AUDIOBOOK_OUTPUT_DIR", "/mnt/storage/audiobooks"
        ),
        "music_default_genre": os.environ.get("MUSIC_DEFAULT_GENRE", ""),
        "music_default_year": None,
        "jellyfin_music_path": os.environ.get("JELLYFIN_MUSIC_PATH", ""),
        "sonarr_blackhole_path": os.environ.get("SONARR_BLACKHOLE_PATH", ""),
        "radarr_blackhole_path": os.environ.get("RADARR_BLACKHOLE_PATH", ""),
    }

    music_year_env = os.environ.get("MUSIC_DEFAULT_YEAR", "").strip()
    if music_year_env:
        try:
            config["music_default_year"] = int(music_year_env)
        except ValueError:
            logger.warning(
                "Invalid MUSIC_DEFAULT_YEAR value '%s'; expected integer", music_year_env
            )

    cookies_path = os.environ.get("COOKIES_PATH", "")
    if cookies_path and os.path.exists(cookies_path):
        config["cookies"] = cookies_path
    elif cookies_path:
        logger.warning(f"Cookies file not found at {cookies_path}, ignoring")

    config_file = os.environ.get("CONFIG_FILE", "config/config.yml")
    if os.path.exists(config_file):
        try:
            with open(config_file, "r") as f:
                file_config = yaml.safe_load(f)
            if file_config and isinstance(file_config, dict):
                if "media" in file_config and isinstance(file_config["media"], dict):
                    for key, value in file_config["media"].items():
                        if key == "output_dir":
                            config["output_dir"] = value
                        elif key == "quality":
                            config["quality"] = value
                        elif key == "use_h265":
                            config["use_h265"] = value
                        elif key == "crf":
                            config["crf"] = int(value)
                        elif key == "clean_filenames":
                            config["clean_filenames"] = value

                if "cookies_path" in file_config:
                    cookies_path = file_config["cookies_path"]
                    if os.path.exists(cookies_path):
                        config["cookies"] = cookies_path
                    else:
                        logger.warning(
                            f"Cookies file not found at {cookies_path}, ignoring"
                        )

                if "defaults" in file_config and isinstance(
                    file_config["defaults"], dict
                ):
                    config["defaults"] = file_config["defaults"]

                if "completed_jobs_limit" in file_config:
                    config["completed_jobs_limit"] = int(
                        file_config["completed_jobs_limit"]
                    )

                if "max_concurrent_jobs" in file_config:
                    config["max_concurrent_jobs"] = int(
                        file_config["max_concurrent_jobs"]
                    )

                if "web" in file_config and isinstance(file_config["web"], dict):
                    for key, value in file_config["web"].items():
                        if key == "enabled":
                            config["web_enabled"] = value
                        elif key == "port":
                            config["web_port"] = int(value)
                        elif key == "host":
                            config["web_host"] = value

                if "jellyfin" in file_config and isinstance(
                    file_config["jellyfin"], dict
                ):
                    for key, value in file_config["jellyfin"].items():
                        if key == "enabled":
                            config["jellyfin_enabled"] = value
                        elif key == "tv_path":
                            config["jellyfin_tv_path"] = value
                        elif key == "movie_path":
                            config["jellyfin_movie_path"] = value
                        elif key == "music_path":
                            config["jellyfin_music_path"] = value
                        elif key == "host":
                            config["jellyfin_host"] = value
                        elif key == "port":
                            config["jellyfin_port"] = str(value)
                        elif key == "api_key":
                            config["jellyfin_api_key"] = value

                if "blackhole" in file_config and isinstance(
                    file_config["blackhole"], dict
                ):
                    for key, value in file_config["blackhole"].items():
                        if key == "sonarr":
                            config["sonarr_blackhole_path"] = value
                        elif key == "radarr":
                            config["radarr_blackhole_path"] = value

                if "sonarr_blackhole_path" in file_config:
                    config["sonarr_blackhole_path"] = file_config["sonarr_blackhole_path"]
                if "radarr_blackhole_path" in file_config:
                    config["radarr_blackhole_path"] = file_config["radarr_blackhole_path"]

                if "tmdb" in file_config and isinstance(file_config["tmdb"], dict):
                    if "api_key" in file_config["tmdb"]:
                        config["tmdb_api_key"] = file_config["tmdb"]["api_key"]

                if "tvdb" in file_config and isinstance(file_config["tvdb"], dict):
                    if "api_key" in file_config["tvdb"]:
                        config["tvdb_api_key"] = file_config["tvdb"]["api_key"]
                    if "pin" in file_config["tvdb"]:
                        config["tvdb_pin"] = file_config["tvdb"].get("pin", "")

                if "imdb" in file_config and isinstance(file_config["imdb"], dict):
                    if "enabled" in file_config["imdb"]:
                        config["imdb_enabled"] = file_config["imdb"]["enabled"]
                    if "api_key" in file_config["imdb"]:
                        config["imdb_api_key"] = file_config["imdb"]["api_key"]

                if "music" in file_config and isinstance(file_config["music"], dict):
                    music_cfg = file_config["music"]
                    if "output_dir" in music_cfg:
                        config["music_output_dir"] = music_cfg["output_dir"]
                    if "default_genre" in music_cfg:
                        config["music_default_genre"] = music_cfg["default_genre"]
                    if "default_year" in music_cfg:
                        try:
                            config["music_default_year"] = int(music_cfg["default_year"])
                        except (TypeError, ValueError):
                            logger.warning(
                                "Invalid music.default_year value '%s'; expected integer",
                                music_cfg["default_year"],
                            )

                if "update_checker" in file_config and isinstance(
                    file_config["update_checker"], dict
                ):
                    uc = file_config["update_checker"]
                    if "enabled" in uc:
                        config["update_checker_enabled"] = uc["enabled"]
                    if "interval_minutes" in uc:
                        config["update_checker_interval"] = int(uc["interval_minutes"])
        except (yaml.YAMLError, IOError) as e:
            logger.error(f"Error loading config file: {e}")

    if not config["output_dir"]:
        raise ValueError("output_dir is required")

    # Ensure output directories are absolute so file serving works regardless of the
    # current working directory
    config["output_dir"] = os.path.abspath(config["output_dir"])
    config["music_output_dir"] = os.path.abspath(config["music_output_dir"])

    if isinstance(config.get("music_default_year"), str) and config["music_default_year"]:
        try:
            config["music_default_year"] = int(config["music_default_year"])
        except ValueError:
            logger.warning(
                "Invalid music_default_year value '%s'; expected integer",
                config["music_default_year"],
            )
            config["music_default_year"] = None

    try:
        validated = ConfigModel(**config)
    except ValidationError as e:
        raise ValueError(f"Invalid configuration: {e}")

    result = validated.dict()
    if os.environ.get("CONFIG_FILE"):
        # Preserve string type for quality when CONFIG_FILE is specified
        result["quality"] = str(validated.quality)
    logger.info(f"Configuration loaded: {result}")
    return result


def _save_config(config: Dict) -> None:
    """Save configuration to YAML file."""
    config_file = os.environ.get("CONFIG_FILE", "config/config.yml")

    # Create config directory if it doesn't exist
    config_dir = os.path.dirname(config_file)
    if config_dir and not os.path.exists(config_dir):
        os.makedirs(config_dir, exist_ok=True)

    # Structure the config for YAML output
    yaml_config = {
        "media": {
            "output_dir": config.get("output_dir", "./media"),
            "quality": int(config.get("quality", 1080)),
            "use_h265": config.get("use_h265", True),
            "crf": int(config.get("crf", 28)),
            "clean_filenames": config.get("clean_filenames", True),
        },
        "cookies_path": config.get("cookies_path", "./config/cookies.txt"),
        "ytdlp_path": config.get("ytdlp_path", "yt-dlp"),
        "web": {
            "enabled": config.get("web_enabled", True),
            "port": int(config.get("web_port", 8000)),
            "host": config.get("web_host", "0.0.0.0"),
        },
        "completed_jobs_limit": int(config.get("completed_jobs_limit", 10)),
        "max_concurrent_jobs": int(config.get("max_concurrent_jobs", 1)),
        "update_checker": {
            "enabled": config.get("update_checker_enabled", False),
            "interval_minutes": int(config.get("update_checker_interval", 60)),
        },
        "jellyfin": {
            "enabled": config.get("jellyfin_enabled", False),
            "tv_path": config.get("jellyfin_tv_path", ""),
            "movie_path": config.get("jellyfin_movie_path", ""),
            "music_path": config.get("jellyfin_music_path", ""),
            "host": config.get("jellyfin_host", "localhost"),
            "port": int(config.get("jellyfin_port", 8096)),
            "api_key": config.get("jellyfin_api_key", ""),
        },
        "tmdb": {
            "api_key": config.get("tmdb_api_key", ""),
        },
        "tvdb": {
            "api_key": config.get("tvdb_api_key", ""),
            "pin": config.get("tvdb_pin", ""),
        },
        "imdb": {
            "enabled": config.get("imdb_enabled", False),
            "api_key": config.get("imdb_api_key", ""),
        },
        "music": {
            "output_dir": config.get("music_output_dir", "./music"),
            "default_genre": config.get("music_default_genre", ""),
            "default_year": config.get("music_default_year") if config.get("music_default_year") else None,
        },
        "blackhole": {
            "sonarr": config.get("sonarr_blackhole_path", ""),
            "radarr": config.get("radarr_blackhole_path", ""),
        },
        "defaults": config.get("defaults", {}),
    }

    try:
        with open(config_file, "w") as f:
            yaml.safe_dump(yaml_config, f, default_flow_style=False, sort_keys=False)
        logger.info(f"Configuration saved to {config_file}")
    except (IOError, yaml.YAMLError) as e:
        logger.error(f"Error saving config file: {e}")
        raise


__all__ = ["_load_config", "_save_config", "logger"]
