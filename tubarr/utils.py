import os
import re
import subprocess
import logging
import signal
from typing import List

logger = logging.getLogger("yt-to-jellyfin")


def log_job(job_id: str, level: int, message: str) -> None:
    """Log a message with job context."""
    logger.log(level, f"Job {job_id}: {message}")


def sanitize_name(name: str) -> str:
    """Sanitize file/directory names to be compatible with file systems."""
    name = name.strip()
    name = name.replace("_", " ")
    sanitized = re.sub(r'[\\/:"*?<>|]', "", name)
    sanitized = re.sub(r"\s+", " ", sanitized)
    return sanitized


def clean_filename(name: str) -> str:
    """Clean up filename for better readability."""
    episode_pattern = r"(S\d+E\d+)"
    episode_match = re.search(episode_pattern, name)
    if not episode_match:
        return name.replace("_", " ")
    parts = re.split(episode_pattern, name, maxsplit=1)
    if len(parts) >= 1 and parts[0]:
        parts[0] = parts[0].replace("_", " ")
        parts[0] = re.sub(r"\s*-\s*", " - ", parts[0])
        parts[0] = re.sub(r"\s+", " ", parts[0])
        parts[0] = parts[0].strip()
    result = ""
    for i, part in enumerate(parts):
        if i > 0 and i % 2 == 1 and parts[i - 1] and not parts[i - 1].endswith(" "):
            result += " " + part
        else:
            result += part
    if result.startswith("S") and re.match(r"^S\d+E\d+", result) and len(parts) > 1:
        if not parts[1].startswith(" "):
            episode_end = re.match(r"^S\d+E\d+", result).end()
            result = result[:episode_end] + " " + result[episode_end:]
    return result


def run_subprocess(cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
    """Run subprocess command ensuring any nested lists are flattened."""
    flattened: List[str] = []
    for part in cmd:
        if isinstance(part, list):
            flattened.extend(part)
        else:
            flattened.append(part)
    return subprocess.run(flattened, **kwargs)


def terminate_process(process: subprocess.Popen) -> None:
    """Terminate a subprocess and its child processes."""
    try:
        if process.poll() is None:
            if hasattr(os, "killpg"):
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            else:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                if hasattr(os, "killpg"):
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                else:
                    process.kill()
    except Exception as exc:  # pragma: no cover - best effort cleanup
        logger.error(f"Failed to terminate process: {exc}")


def check_dependencies(ytdlp_path: str, extra: List[str] = None) -> bool:
    """Check if all required dependencies are installed."""
    dependencies = ["ffmpeg", "convert", "montage"]
    if extra:
        dependencies.extend(extra)

    logger.info(f"Using yt-dlp path: {ytdlp_path}")
    if ytdlp_path.startswith("/"):
        if not os.path.exists(ytdlp_path):
            logger.error(f"yt-dlp not found at path: {ytdlp_path}")
            return False
        if not os.access(ytdlp_path, os.X_OK):
            logger.error(f"yt-dlp is not executable: {ytdlp_path}")
            return False
        logger.info(f"Found yt-dlp at: {ytdlp_path}")
    else:
        dependencies.append(ytdlp_path)

    for cmd in dependencies:
        try:
            result = subprocess.run(
                ["which", cmd], check=True, capture_output=True, text=True
            )
            logger.info(f"Found dependency {cmd} at: {result.stdout.strip()}")
        except subprocess.CalledProcessError:
            logger.error(f"Required dependency not found: {cmd}")
            return False
    return True


__all__ = [
    "sanitize_name",
    "clean_filename",
    "check_dependencies",
    "run_subprocess",
    "terminate_process",
    "logger",
    "log_job",
]
