#!/usr/bin/env python3
"""YT-to-Jellyfin application entrypoint."""

import os
import sys
import argparse

from tubarr.web import app, ytj
from tubarr.core import YTToJellyfin, DownloadJob, logger

__all__ = ["app", "ytj", "YTToJellyfin", "DownloadJob", "main"]


def main():
    """Parse command line arguments and execute the application."""
    parser = argparse.ArgumentParser(
        description="Download YouTube playlists as TV show episodes for Jellyfin"
    )
    parser.add_argument(
        "--web-only", action="store_true", help="Start only the web interface"
    )
    parser.add_argument("--url", help="YouTube playlist URL")
    parser.add_argument("--show-name", help="TV show name")
    parser.add_argument("--season-num", help="Season number (e.g., 01)")
    parser.add_argument("--episode-start", help="Episode start number (e.g., 01)")
    parser.add_argument("--output-dir", help="Output directory")
    parser.add_argument("--quality", help="Video quality (720, 1080, etc.)")
    parser.add_argument(
        "--no-h265", action="store_true", help="Disable H.265 conversion"
    )
    parser.add_argument("--crf", type=int, help="CRF value for H.265 conversion")
    parser.add_argument("--config", help="Path to config file")
    parser.add_argument(
        "--check-updates",
        action="store_true",
        help="Check registered playlists for new videos",
    )

    # Normal commandline usage still supported as before
    parser.add_argument("url_pos", nargs="?", help="YouTube playlist URL (positional)")
    parser.add_argument("show_name_pos", nargs="?", help="TV show name (positional)")
    parser.add_argument("season_num_pos", nargs="?", help="Season number (positional)")
    parser.add_argument(
        "episode_start_pos", nargs="?", help="Episode start number (positional)"
    )

    args = parser.parse_args()

    # Set environment variables from command line args if provided
    if args.output_dir:
        os.environ["OUTPUT_DIR"] = args.output_dir
    if args.quality:
        os.environ["VIDEO_QUALITY"] = args.quality
    if args.no_h265:
        os.environ["USE_H265"] = "false"
    if args.crf:
        os.environ["CRF"] = str(args.crf)
    if args.config:
        os.environ["CONFIG_FILE"] = args.config

    if args.check_updates:
        ytj.check_playlist_updates()
        return 0

    # Web-only mode
    if args.web_only or ytj.config.get("web_enabled", True):
        # Start web interface
        host = ytj.config.get("web_host", "0.0.0.0")
        port = ytj.config.get("web_port", 8000)

        if args.web_only:
            logger.info(f"Starting web interface on {host}:{port}")
            app.run(host=host, port=port, debug=False)
            return 0

    # Command-line mode if URL is provided
    url = args.url or args.url_pos
    show_name = args.show_name or args.show_name_pos
    season_num = args.season_num or args.season_num_pos
    episode_start = args.episode_start or args.episode_start_pos

    # Use defaults from config if available
    if (
        not url
        and "defaults" in ytj.config
        and "playlist_url" in ytj.config["defaults"]
    ):
        url = ytj.config["defaults"]["playlist_url"]
    if (
        not show_name
        and "defaults" in ytj.config
        and "show_name" in ytj.config["defaults"]
    ):
        show_name = ytj.config["defaults"]["show_name"]
    if (
        not season_num
        and "defaults" in ytj.config
        and "season_num" in ytj.config["defaults"]
    ):
        season_num = ytj.config["defaults"]["season_num"]
    if (
        not episode_start
        and "defaults" in ytj.config
        and "episode_start" in ytj.config["defaults"]
    ):
        episode_start = ytj.config["defaults"]["episode_start"]

    if url and show_name and season_num and episode_start:
        try:
            episode_start_int = int(episode_start)
        except ValueError:
            logger.error("Episode start must be a number")
            return 1

        success = ytj.process(url, show_name, season_num, episode_start_int)

        # Always start web interface after processing if enabled
        if ytj.config.get("web_enabled", True) and not args.web_only:
            host = ytj.config.get("web_host", "0.0.0.0")
            port = ytj.config.get("web_port", 8000)
            logger.info(f"Starting web interface on {host}:{port}")
            app.run(host=host, port=port, debug=False)

        return 0 if success else 1
    elif ytj.config.get("web_enabled", True):
        # No command-line parameters, but web is enabled
        host = ytj.config.get("web_host", "0.0.0.0")
        port = ytj.config.get("web_port", 8000)
        logger.info(f"Starting web interface on {host}:{port}")
        app.run(host=host, port=port, debug=False)
        return 0
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
