import os
import yaml
import logging
from typing import Dict, Optional
from pydantic import BaseModel, Field, ValidationError, validator

logger = logging.getLogger("yt-to-jellyfin")


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
    jellyfin_host: str = ""
    jellyfin_port: int = Field(8096, ge=1, le=65535)
    jellyfin_api_key: str = ""
    tmdb_api_key: str = ""
    imdb_enabled: bool = False
    imdb_api_key: str = ""
    clean_filenames: bool = True
    defaults: Optional[Dict[str, str]] = Field(default_factory=dict)

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
        "clean_filenames": os.environ.get("CLEAN_FILENAMES", "true").lower() == "true",
    }

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
                        elif key == "host":
                            config["jellyfin_host"] = value
                        elif key == "port":
                            config["jellyfin_port"] = str(value)
                        elif key == "api_key":
                            config["jellyfin_api_key"] = value

                if "tmdb" in file_config and isinstance(file_config["tmdb"], dict):
                    if "api_key" in file_config["tmdb"]:
                        config["tmdb_api_key"] = file_config["tmdb"]["api_key"]

                if "imdb" in file_config and isinstance(file_config["imdb"], dict):
                    if "enabled" in file_config["imdb"]:
                        config["imdb_enabled"] = file_config["imdb"]["enabled"]
                    if "api_key" in file_config["imdb"]:
                        config["imdb_api_key"] = file_config["imdb"]["api_key"]

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

    # Ensure output_dir is absolute so file serving works regardless of the
    # current working directory
    config["output_dir"] = os.path.abspath(config["output_dir"])

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


__all__ = ["_load_config", "logger"]
