from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_from_directory,
)
import os

from .core import logger, YTToJellyfin

# Create Flask application for web interface
# Determine the repository root so the web assets can be located correctly
_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

app = Flask(
    __name__,
    template_folder=os.path.join(_BASE_DIR, "web", "templates"),
    static_folder=os.path.join(_BASE_DIR, "web", "static"),
)

ytj = YTToJellyfin()


@app.route("/")
def index():
    """Main web interface page."""
    return render_template("index.html", jobs=ytj.get_jobs(), media=ytj.list_media())


@app.route("/jobs", methods=["GET", "POST"])
def jobs():
    """Handle job listing and creation."""
    if request.method == "POST":
        # Create new job
        playlist_url = request.form.get("playlist_url")
        show_name = request.form.get("show_name")
        season_num = request.form.get("season_num")
        episode_start = request.form.get("episode_start")
        playlist_start = request.form.get("playlist_start")
        track_playlist = request.form.get("track_playlist", "true").lower() != "false"

        if not playlist_url or not show_name or not season_num or not episode_start:
            return jsonify({"error": "Missing required parameters"}), 400

        playlist_start_int = int(playlist_start) if playlist_start else None
        if playlist_start_int is not None:
            job_id = ytj.create_job(
                playlist_url,
                show_name,
                season_num,
                episode_start,
                playlist_start_int,
                track_playlist,
            )
        else:
            job_id = ytj.create_job(
                playlist_url,
                show_name,
                season_num,
                episode_start,
                playlist_start=None,
                track_playlist=track_playlist,
            )
        return jsonify({"job_id": job_id})
    else:
        # Get all jobs
        return jsonify(ytj.get_jobs())


@app.route("/movies", methods=["GET", "POST"])
def movies():
    if request.method == "POST":
        video_url = request.form.get("video_url") or (request.json or {}).get(
            "video_url"
        )
        movie_name = request.form.get("movie_name") or (request.json or {}).get(
            "movie_name"
        )
        if not video_url or not movie_name:
            return jsonify({"error": "Missing required parameters"}), 400
        if ytj._is_playlist_url(video_url):
            videos = ytj.get_playlist_videos(video_url)
            job_ids = []
            for v in videos:
                vid = v.get("id")
                title = v.get("title") or movie_name
                if not vid:
                    continue
                url = f"https://www.youtube.com/watch?v={vid}"
                job_ids.append(ytj.create_movie_job(url, title))
            return jsonify({"job_ids": job_ids})
        else:
            job_id = ytj.create_movie_job(video_url, movie_name)
            return jsonify({"job_id": job_id})
    else:
        return jsonify(ytj.list_movies())


@app.route("/music/jobs", methods=["GET", "POST"])
def music_jobs():
    """Create or list music download jobs."""

    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        if not data:
            return jsonify({"error": "Missing request payload"}), 400
        try:
            job_id = ytj.create_music_job(data)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"job_id": job_id})

    jobs = [job for job in ytj.get_jobs() if job.get("media_type") == "music"]
    return jsonify(jobs)


@app.route("/music/jobs/<job_id>", methods=["GET"])
def music_job_detail(job_id):
    """Return details for a single music job."""

    job = ytj.get_job(job_id)
    if not job or job.get("media_type") != "music":
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)


@app.route("/music/playlists/info", methods=["GET"])
def music_playlist_info():
    """Return playlist metadata for music requests."""

    url = request.args.get("url")
    if not url:
        return jsonify({"error": "Missing url"}), 400
    info = ytj.get_music_playlist_info(url)
    return jsonify(info)


@app.route("/jobs/<job_id>", methods=["GET", "DELETE"])
def job_detail(job_id):
    """Get or modify a specific job."""
    if request.method == "DELETE":
        if ytj.cancel_job(job_id):
            return jsonify({"success": True})
        return jsonify({"error": "Job not found"}), 404

    job = ytj.get_job(job_id)
    if job:
        return jsonify(job)
    return jsonify({"error": "Job not found"}), 404


@app.route("/media", methods=["GET"])
def media():
    """List all media files."""
    return jsonify(ytj.list_media())


@app.route("/media_files/<path:filename>")
def media_files(filename):
    """Serve media files such as posters."""
    output_dir = ytj.config.get("output_dir", "")
    return send_from_directory(output_dir, filename)


@app.route("/playlists", methods=["GET"])
def playlists():
    """Return registered playlists."""
    return jsonify(ytj.list_playlists())


@app.route("/subscriptions", methods=["GET", "POST"])
def subscriptions():
    """List subscriptions or create a new subscription."""
    if request.method == "POST":
        data = request.get_json(silent=True) or request.form
        channel_url = data.get("channel_url")
        show_name = data.get("show_name")
        retention_type = data.get("retention_type", "keep_all")
        retention_value = data.get("retention_value")
        try:
            subscription_id = ytj.create_subscription(
                channel_url, show_name, retention_type, retention_value
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"subscription_id": subscription_id})
    return jsonify(ytj.list_subscriptions())


@app.route("/subscriptions/<sid>", methods=["PUT", "DELETE"])
def subscription_modify(sid):
    """Update or remove a subscription."""
    if request.method == "DELETE":
        if ytj.remove_subscription(sid):
            return jsonify({"success": True})
        return jsonify({"error": "Subscription not found"}), 404

    data = request.get_json() or {}
    show_name = data.get("show_name")
    retention_type = data.get("retention_type")
    retention_value = data.get("retention_value")
    enabled = data.get("enabled")
    if isinstance(enabled, str):
        enabled = enabled.lower() in {"true", "1", "yes", "on"}
    try:
        updated = ytj.update_subscription(
            sid,
            show_name=show_name,
            retention_type=retention_type,
            retention_value=retention_value,
            enabled=enabled,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if not updated:
        return jsonify({"error": "Subscription not found"}), 404
    return jsonify({"success": True})


@app.route("/playlists/<pid>", methods=["PUT", "DELETE"])
def playlist_modify(pid):
    """Enable/disable or remove a playlist."""
    if request.method == "PUT":
        data = request.get_json() or {}
        if "enabled" not in data:
            return jsonify({"error": "Missing enabled flag"}), 400
        if ytj.set_playlist_enabled(pid, bool(data["enabled"])):
            return jsonify({"success": True})
        return jsonify({"error": "Playlist not found"}), 404
    else:  # DELETE
        if ytj.remove_playlist(pid):
            return jsonify({"success": True})
        return jsonify({"error": "Playlist not found"}), 404


@app.route("/playlist_info")
def playlist_info():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "Missing url"}), 400
    return jsonify(ytj.get_playlist_videos(url))


@app.route("/playlists/check", methods=["POST"])
def playlists_check():
    """Check all playlists for updates and return created job ids."""
    jobs = ytj.check_playlist_updates()
    return jsonify({"created_jobs": jobs})


@app.route("/config", methods=["GET", "PUT"])
def config():
    """Get or update configuration."""
    if request.method == "PUT":
        # Get updated configuration from request
        new_config = request.json
        if new_config:
            # Update allowed configuration settings
            allowed_keys = [
                "output_dir",
                "quality",
                "use_h265",
                "crf",
                "web_port",
                "completed_jobs_limit",
                "max_concurrent_jobs",
                "jellyfin_enabled",
                "jellyfin_tv_path",
                "jellyfin_movie_path",
                "jellyfin_host",
                "jellyfin_port",
                "jellyfin_api_key",
                "tmdb_api_key",
                "imdb_enabled",
                "imdb_api_key",
                "clean_filenames",
                "update_checker_enabled",
                "update_checker_interval",
            ]

            should_restart_update = False
            # Update only allowed keys
            for key in allowed_keys:
                if key in new_config:
                    if key in [
                        "jellyfin_enabled",
                        "use_h265",
                        "clean_filenames",
                        "update_checker_enabled",
                    ]:
                        ytj.config[key] = new_config[key] is True
                    elif key in [
                        "crf",
                        "web_port",
                        "completed_jobs_limit",
                        "max_concurrent_jobs",
                        "update_checker_interval",
                    ]:
                        ytj.config[key] = int(new_config[key])
                    else:
                        ytj.config[key] = new_config[key]

                    if key in ["update_checker_enabled", "update_checker_interval"]:
                        should_restart_update = True

            # Special handling for cookies_path
            if "cookies_path" in new_config:
                cookies_path = new_config["cookies_path"]
                # Store the path for display purposes
                ytj.config["cookies_path"] = cookies_path

                # Check if the file exists and update cookies if it does
                if os.path.exists(cookies_path):
                    ytj.config["cookies"] = cookies_path
                    logger.info(f"Updated cookies file path to: {cookies_path}")
                else:
                    # Clear cookies if path is invalid
                    ytj.config["cookies"] = ""
                    logger.warning(
                        f"Cookies file not found at {cookies_path}, not using cookies"
                    )

            if should_restart_update:
                if ytj.update_thread and ytj.update_thread.is_alive():
                    ytj.stop_update_checker()
                if ytj.config.get("update_checker_enabled"):
                    ytj.start_update_checker()

            return jsonify({"success": True, "message": "Configuration updated"})

        return jsonify({"error": "Invalid configuration data"}), 400
    else:
        # Get configuration
        safe_config = {k: v for k, v in ytj.config.items()}
        # Add cookies path for rendering the UI
        if "cookies_path" not in safe_config and "cookies" in safe_config:
            safe_config["cookies_path"] = safe_config["cookies"]

        # For security, don't expose actual cookie file content or path
        if "cookies" in safe_config:
            del safe_config["cookies"]

        return jsonify(safe_config)


@app.route("/history")
def history():
    """Return completed, failed and cancelled jobs sorted by creation time."""
    finished = [
        j.to_dict(include_messages=False)
        for j in ytj.jobs.values()
        if j.status in {"completed", "failed", "cancelled"}
    ]
    finished.sort(key=lambda j: j["created_at"])
    return jsonify(finished)


__all__ = ["app", "ytj", "history"]
