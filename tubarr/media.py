import os
import json
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from .config import logger
from .utils import sanitize_name, clean_filename, run_subprocess


def create_folder_structure(app, show_name: str, season_num: str) -> str:
    folder = (
        Path(app.config["output_dir"])
        / sanitize_name(show_name)
        / f"Season {season_num}"
    )
    folder.mkdir(parents=True, exist_ok=True)
    return str(folder)


def create_movie_folder(app, movie_name: str) -> str:
    folder = Path(app.config["output_dir"]) / sanitize_name(movie_name)
    folder.mkdir(parents=True, exist_ok=True)
    return str(folder)


def download_playlist(
    app,
    playlist_url: str,
    folder: str,
    season_num: str,
    job_id: str,
    playlist_start: Optional[int] = None,
) -> bool:
    output_template = f"{folder}/%(title)s S{season_num}E%(playlist_index)02d.%(ext)s"
    ytdlp_path = app.config["ytdlp_path"]
    if not os.path.isabs(ytdlp_path):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        local_ytdlp = os.path.join(script_dir, ytdlp_path)
        if os.path.exists(local_ytdlp) and os.access(local_ytdlp, os.X_OK):
            ytdlp_path = local_ytdlp
    logger.info(f"Using yt-dlp from: {ytdlp_path}")
    cmd = [
        ytdlp_path,
        "--ignore-errors",
        "--no-warnings",
        (
            f'-f bestvideo[height<={app.config["quality"]}]'
            f'+bestaudio/best[height<={app.config["quality"]}]'
        ),
        "-o",
        output_template,
        "--write-info-json",
        "--restrict-filenames",
        "--merge-output-format",
        "mp4",
        "--progress",
        "--no-cookies-from-browser",
        playlist_url,
    ]
    archive_file = app._get_archive_file(playlist_url)
    os.makedirs(os.path.dirname(archive_file), exist_ok=True)
    cmd.extend(["--download-archive", archive_file])
    if playlist_start:
        cmd.extend(["--playlist-start", str(playlist_start)])
    elif not os.path.exists(archive_file):
        existing_max = app._get_existing_max_index(folder, season_num)
        if existing_max:
            cmd.extend(["--playlist-start", str(existing_max + 1)])
    if app.config["cookies"] and os.path.exists(app.config["cookies"]):
        cmd.insert(1, f'--cookies={app.config["cookies"]}')
    else:
        cmd.insert(1, "--no-cookies")
    job = app.jobs.get(job_id)
    if job:
        job.update(
            status="downloading",
            stage="downloading",
            progress=0,
            stage_progress=0,
            detailed_status="Starting download of playlist",
            message=f"Starting download of playlist: {playlist_url}",
        )
    logger.info(f"Starting download of playlist: {playlist_url}")
    current_file = ""
    total_files = 0
    processed_files = 0
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
        if job:
            job.process = process
        for line in process.stdout:
            if job and job.status == "cancelled":
                process.terminate()
                break
            line = line.strip()
            logger.info(line)
            if job:
                if "[download]" in line and "Destination:" in line:
                    try:
                        file_match = re.search(r"Destination:\s+(.+)", line)
                        if file_match:
                            current_file = os.path.basename(file_match.group(1))
                            processed_files += 1
                            if job.remaining_files:
                                job.remaining_files.pop(0)
                            job.update(
                                file_name=current_file,
                                processed_files=processed_files,
                                detailed_status=f"Downloading: {current_file}",
                                message=f"Downloading file: {current_file}",
                            )
                    except (ValueError, AttributeError) as e:
                        logger.error(f"Error parsing destination: {e}")
                elif "[download]" in line and "of" in line and "item" in line:
                    try:
                        total_match = re.search(r"of\s+(\d+)\s+item", line)
                        if total_match:
                            total_files = int(total_match.group(1))
                            job.update(total_files=total_files)
                    except (ValueError, AttributeError) as e:
                        logger.error(f"Error parsing total files: {e}")
                elif "%" in line:
                    try:
                        progress_str = re.search(r"(\d+\.\d+)%", line)
                        if progress_str:
                            file_progress = float(progress_str.group(1))
                            if total_files > 0:
                                overall_progress = min(
                                    99,
                                    ((processed_files - 1) / total_files * 100)
                                    + (file_progress / total_files),
                                )
                            else:
                                overall_progress = file_progress
                            job.update(
                                progress=overall_progress,
                                stage_progress=file_progress,
                                message=line,
                                detailed_status=(
                                    f"Downloading: {current_file} "
                                    f"({file_progress:.1f}%)"
                                ),
                            )
                    except (ValueError, AttributeError) as e:
                        logger.error(f"Error parsing progress: {e}")
                        job.update(message=line)
                else:
                    job.update(message=line)
        process.wait()
        if job:
            job.process = None
        if process.returncode != 0:
            if job:
                job.update(
                    status="failed",
                    stage="failed",
                    detailed_status="Download failed",
                    message=f"Download failed with return code {process.returncode}",
                )
            logger.error(
                f"Error downloading playlist, return code: {process.returncode}"
            )
            return False
        if job:
            job.update(
                status="downloaded",
                stage="downloading",
                progress=100,
                stage_progress=100,
                detailed_status="Download completed successfully",
                message="Download completed successfully",
            )
        return True
    except subprocess.SubprocessError as e:
        if job:
            job.process = None
            job.update(status="failed", message=f"Download failed: {str(e)}")
        logger.error(f"Error downloading playlist: {e}")
        return False


def process_metadata(
    app, folder: str, show_name: str, season_num: str, episode_start: int, job_id: str
) -> None:
    job = app.jobs.get(job_id)
    if job:
        job.update(
            status="processing_metadata",
            stage="processing_metadata",
            progress=0,
            stage_progress=0,
            detailed_status="Processing metadata from videos",
            message="Processing metadata and creating NFO files",
        )
    json_files = list(Path(folder).glob("*.info.json"))
    if not json_files:
        if job:
            job.update(
                message="Warning: No JSON metadata files found",
                detailed_status="No metadata files found",
            )
        logger.warning("No JSON metadata files found")
        return
    with open(json_files[0], "r") as f:
        first_data = json.load(f)
        first_index = first_data.get("playlist_index", 1)
    episode_offset = episode_start - first_index
    total_files = len(json_files)
    if job:
        job.update(
            total_files=total_files,
            detailed_status=f"Processing metadata for {total_files} videos",
        )
    for i, json_file in enumerate(json_files):
        with open(json_file, "r") as f:
            data = json.load(f)
        title = data.get("title", "Unknown Title")
        description = (
            data.get("description", "").split("\n")[0]
            if data.get("description")
            else ""
        )
        upload_date = data.get("upload_date", "")
        if upload_date:
            try:
                air_date = datetime.strptime(upload_date, "%Y%m%d").strftime("%Y-%m-%d")
            except ValueError:
                air_date = ""
        else:
            air_date = ""
        original_ep = data.get("playlist_index", 0)
        new_ep = original_ep + episode_offset
        new_ep_padded = f"{new_ep:02d}"
        base_file = str(json_file).replace(".info.json", "")
        new_base = re.sub(
            rf"(\s?)?(S{season_num}E)[0-9]+",
            lambda m: f"{m.group(1) or ' '}{m.group(2)}{new_ep_padded}",
            base_file,
        )
        file_name = os.path.basename(new_base)
        if job:
            job.update(
                file_name=file_name,
                processed_files=i + 1,
                detailed_status=f"Processing metadata: {file_name}",
                message=f"Processing metadata for {title}",
            )
        for ext in ["mp4", "mkv", "webm"]:
            original = f"{base_file}.{ext}"
            if os.path.exists(original):
                basename = os.path.basename(new_base)
                if app.config.get("clean_filenames", True):
                    basename = clean_filename(basename)
                new_file = os.path.join(os.path.dirname(new_base), f"{basename}.{ext}")
                os.rename(original, new_file)
                if job:
                    job.update(message=f"Renamed file to {os.path.basename(new_file)}")
                break
        nfo_content = (
            "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>\n"
            "<episodedetails>\n"
            f"  <title>{title}</title>\n"
            f"  <season>{season_num}</season>\n"
            f"  <episode>{new_ep_padded}</episode>\n"
            f"  <plot>{description}</plot>\n"
            f"  <aired>{air_date}</aired>\n"
            "  <studio>YouTube</studio>\n"
            f"  <showtitle>{show_name}</showtitle>\n"
            "</episodedetails>\n"
        )
        basename = os.path.basename(new_base)
        if app.config.get("clean_filenames", True):
            basename = clean_filename(basename)
        nfo_file = os.path.join(os.path.dirname(new_base), f"{basename}.nfo")
        with open(nfo_file, "w") as f:
            f.write(nfo_content)
        if job:
            job.update(message=f"Created NFO file for {title}")
        os.remove(json_file)
        if job and total_files:
            progress = int((i + 1) / total_files * 100)
            job.update(
                progress=progress,
                stage_progress=progress,
                detailed_status=f"Processed {i+1} of {total_files} files",
            )

    last_episode = episode_start + total_files - 1
    app.update_last_episode(show_name, season_num, last_episode)


def convert_video_files(app, folder: str, season_num: str, job_id: str) -> None:
    if not app.config["use_h265"]:
        logger.info("H.265 conversion disabled, skipping")
        job = app.jobs.get(job_id)
        if job:
            job.update(
                message="H.265 conversion disabled, skipping",
                detailed_status="H.265 conversion disabled",
            )
        return
    job = app.jobs.get(job_id)
    if job:
        job.update(
            status="converting",
            stage="converting",
            progress=0,
            stage_progress=0,
            detailed_status="Preparing video conversion to H.265",
            message="Starting video conversion to H.265",
        )
    video_files = []
    for ext in ["webm", "mp4"]:
        video_files.extend(list(Path(folder).glob(f"*S{season_num}E*.{ext}")))
    total_files = len(video_files)
    if total_files == 0:
        if job:
            job.update(
                message="No video files found for conversion",
                detailed_status="No video files to convert",
            )
        return
    if job:
        job.update(
            total_files=total_files,
            detailed_status=f"Converting {total_files} video files to H.265",
        )
    for i, video in enumerate(video_files):
        ext = str(video).rsplit(".", 1)[1].lower()
        if ext == "mp4":
            probe_cmd = [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_name",
                "-of",
                "json",
                str(video),
            ]
            result = subprocess.run(probe_cmd, capture_output=True, text=True)
            codec = (
                json.loads(result.stdout).get("streams", [{}])[0].get("codec_name", "")
            )
            if codec in ["hevc", "h265"]:
                logger.info(f"Skipping already H.265 encoded file: {video}")
                if job:
                    job.update(
                        processed_files=i + 1,
                        message=(
                            "Skipping already H.265 encoded file: "
                            f"{os.path.basename(str(video))}"
                        ),
                    )
                continue
        base = str(video).rsplit(".", 1)[0]
        temp_file = f"{base}.temp.mp4"
        cmd = [
            "ffmpeg",
            "-i",
            str(video),
            "-c:v",
            "libx265",
            "-preset",
            "medium",
            "-crf",
            str(app.config["crf"]),
            "-tag:v",
            "hvc1",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            temp_file,
        ]
        filename = os.path.basename(str(video))
        if job:
            job.update(
                file_name=filename,
                processed_files=i + 1,
                detailed_status=(
                    f"Converting {filename} to H.265 (file {i+1}/{total_files})"
                ),
                message=(
                    f"Converting {filename} to H.265 ({i+1}/{total_files})"
                ),
            )
        logger.info(f"Converting {video} to H.265")
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
            )
            if job:
                job.process = process
            for line in process.stdout:
                if job and job.status == "cancelled":
                    process.terminate()
                    break
                logger.debug(line.strip())
                if job and "time=" in line:
                    try:
                        time_str = re.search(r"time=(\d+:\d+:\d+\.\d+)", line)
                        if time_str:
                            time_parts = time_str.group(1).split(":")
                            seconds = (
                                float(time_parts[0]) * 3600
                                + float(time_parts[1]) * 60
                                + float(time_parts[2])
                            )
                            duration_cmd = [
                                "ffprobe",
                                "-v",
                                "error",
                                "-show_entries",
                                "format=duration",
                                "-of",
                                "default=noprint_wrappers=1:nokey=1",
                                str(video),
                            ]
                            duration_result = subprocess.run(
                                duration_cmd, capture_output=True, text=True, check=True
                            )
                            duration = float(duration_result.stdout.strip())
                            if duration > 0:
                                file_progress = min(100, int(seconds / duration * 100))
                                total_progress = min(
                                    99,
                                    ((i) / total_files * 100)
                                    + (file_progress / total_files),
                                )
                                job.update(
                                    progress=total_progress,
                                    stage_progress=file_progress,
                                    detailed_status=(
                                        f"Converting {filename}: {file_progress}% "
                                        f"(file {i+1}/{total_files})"
                                    ),
                                )
                                if file_progress % 20 == 0:
                                    job.update(
                                        message=(
                                            f"Converting {filename}: {file_progress}% "
                                            f"complete"
                                        )
                                    )
                    except Exception as e:
                        logger.error(f"Error parsing progress: {e}")
            process.wait()
            if job:
                job.process = None
            if process.returncode == 0:
                os.rename(temp_file, f"{base}.mp4")
                if str(video) != f"{base}.mp4":
                    os.remove(video)
                logger.info(f"Converted: {video} → {base}.mp4")
                if job:
                    job.update(
                        message=f"Successfully converted {filename} to H.265",
                        detailed_status=f"Converted {i+1}/{total_files} files",
                    )
            else:
                logger.error(
                    f"Failed to convert {video}, return code: {process.returncode}"
                )
                if job:
                    job.update(
                        message=(
                            "Failed to convert "
                            f"{filename}, return code: {process.returncode}"
                        ),
                        detailed_status=f"Error converting {filename}",
                    )
                if os.path.exists(temp_file):
                    os.remove(temp_file)
        except subprocess.SubprocessError as e:
            logger.error(f"Failed to convert {video}: {e}")
            if job:
                job.process = None
                job.update(
                    message=f"Failed to convert {filename}: {str(e)}",
                    detailed_status=f"Error converting {filename}",
                )
            if os.path.exists(temp_file):
                os.remove(temp_file)
    if job:
        job.update(
            progress=100,
            stage_progress=100,
            detailed_status="Video conversion completed",
            message="Video conversion completed",
        )


from . import tmdb


def process_movie_metadata(app, folder: str, movie_name: str, job_id: str) -> None:
    job = app.jobs.get(job_id)
    if job:
        job.update(
            status="processing_metadata",
            stage="processing_metadata",
            progress=0,
            stage_progress=0,
            detailed_status="Processing movie metadata",
            message="Processing movie metadata",
        )
    json_files = list(Path(folder).glob("*.info.json"))
    if not json_files:
        if job:
            job.update(message="Warning: No JSON metadata file found")
        logger.warning("No JSON metadata file found")
        return
    with open(json_files[0], "r") as f:
        data = json.load(f)
    description = data.get("description", "").split("\n")[0] if data.get("description") else ""
    upload_date = data.get("upload_date", "")
    year = upload_date[:4] if len(upload_date) >= 4 else ""
    video_id = data.get("id", "")

    tmdb_data = None
    api_key = app.config.get("tmdb_api_key")
    if api_key:
        search_title = tmdb.clean_title(movie_name)
        try:
            result = tmdb.search_movie(search_title, year, api_key)
            if result:
                tmdb_data = tmdb.fetch_movie_details(result["id"], api_key)
        except Exception as e:  # network or api errors should not fail job
            logger.error(f"TMDb lookup failed: {e}")

    if tmdb_data:
        title = tmdb_data.get("title", movie_name)
        plot = tmdb_data.get("overview", description)
        year = tmdb_data.get("release_date", "")[:4]
        tmdb_id = tmdb_data.get("id")
        poster_path = tmdb_data.get("poster_path")
        genres = [g["name"] for g in tmdb_data.get("genres", [])]
        actors = [c.get("name") for c in tmdb_data.get("credits", {}).get("cast", [])[:5]]
        base_name = f"{title}"
        if year:
            base_name += f" ({year})"
        if tmdb_id:
            base_name += f" [tmdb{tmdb_id}]"
        base_name = clean_filename(sanitize_name(base_name))
    else:
        title = movie_name
        plot = description
        tmdb_id = video_id
        genres = []
        actors = []
        base_name = movie_name
        if year:
            base_name += f" ({year})"
        if video_id:
            base_name += f" [{video_id}]"
        base_name = clean_filename(sanitize_name(base_name))
    video_file = None
    for ext in ["mp4", "mkv", "webm"]:
        files = list(Path(folder).glob(f"*.{ext}"))
        if files:
            video_file = files[0]
            break
    if video_file:
        new_file = Path(folder) / f"{base_name}{video_file.suffix}"
        os.rename(video_file, new_file)
        if job:
            job.update(message=f"Renamed movie file to {new_file.name}")
    if tmdb_data and poster_path:
        try:
            tmdb.download_poster(poster_path, str(Path(folder) / "poster.jpg"), api_key)
        except Exception as e:
            logger.error(f"Failed to download poster: {e}")
    nfo_content = (
        "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>\n"
        "<movie>\n"
        f"  <title>{title}</title>\n"
        f"  <plot>{plot}</plot>\n"
        f"  <studio>YouTube</studio>\n"
    )
    if year:
        nfo_content += f"  <year>{year}</year>\n"
    if tmdb_id:
        nfo_content += f"  <id>{tmdb_id}</id>\n"
    for g in genres:
        nfo_content += f"  <genre>{g}</genre>\n"
    for actor in actors:
        nfo_content += "  <actor>\n    <name>{}</name>\n  </actor>\n".format(actor)
    nfo_content += "</movie>\n"
    with open(Path(folder) / "movie.nfo", "w") as f:
        f.write(nfo_content)
    if job:
        job.update(progress=100, stage_progress=100, message="Movie metadata processed")
    for jf in json_files:
        os.remove(jf)


def generate_movie_artwork(app, folder: str, job_id: str) -> None:
    """Generate a simple poster for a movie from extracted frames."""
    job = app.jobs.get(job_id)
    if job:
        job.update(status="generating_artwork", message="Generating movie artwork")

    video_files = []
    for ext in ["mp4", "mkv", "webm"]:
        video_files.extend(Path(folder).glob(f"*.{ext}"))

    if not video_files:
        logger.warning("No movie file found for artwork generation")
        if job:
            job.update(message="No movie file found for artwork generation")
        return

    movie_file = video_files[0]
    try:
        frames_dir = os.path.join(app.temp_dir, "movie_frames")
        os.makedirs(frames_dir, exist_ok=True)
        frame_pattern = os.path.join(frames_dir, "frame_%03d.jpg")
        run_subprocess(
            [
                "ffmpeg",
                "-i",
                str(movie_file),
                "-vf",
                r"select=not(mod(n\,1000)),scale=640:360",
                "-vframes",
                "3",
                frame_pattern,
            ],
            check=True,
            capture_output=True,
        )
        frame_files = sorted(Path(frames_dir).glob("frame_*.jpg"))
        if frame_files:
            poster_path = Path(folder) / "poster.jpg"
            run_subprocess(
                ["convert", *[str(f) for f in frame_files], "-append", str(poster_path)],
                check=True,
            )
            if job:
                job.update(progress=100, message="Created movie poster")
    except (subprocess.CalledProcessError, OSError) as e:
        logger.error(f"Error generating movie artwork: {e}")
        if job:
            job.update(message=f"Error generating movie artwork: {str(e)}")


def generate_artwork(
    app, folder: str, show_name: str, season_num: str, job_id: str
) -> None:
    job = app.jobs.get(job_id)
    if job:
        job.update(
            status="generating_artwork", message="Generating thumbnails and artwork"
        )
    show_folder = str(Path(folder).parent)
    episodes = list(Path(folder).glob(f"*S{season_num}E*.mp4"))
    if not episodes:
        logger.warning("No episodes found for artwork generation")
        if job:
            job.update(message="No episodes found for artwork generation")
        return
    try:
        if job:
            job.update(progress=30, message="Creating show and season artwork")
        temp_posters = []
        for i, episode in enumerate(episodes[:1]):
            poster_file = os.path.join(app.temp_dir, f"tmp_poster_{i:03d}.jpg")
            filter_str = r"select=not(mod(n\,1000)),scale=640:360"
            run_subprocess(
                [
                    "ffmpeg",
                    "-i",
                    str(episode),
                    "-vf",
                    filter_str,
                    "-vframes",
                    "3",
                    poster_file,
                ],
                check=True,
                capture_output=True,
            )
            temp_posters.append(poster_file)
        if temp_posters:
            poster_path = os.path.join(show_folder, "poster.jpg")
            run_subprocess(
                [
                    "convert",
                    *temp_posters,
                    "-gravity",
                    "Center",
                    "-background",
                    "Black",
                    "-resize",
                    "1000x1500^",
                    "-extent",
                    "1000x1500",
                    "-pointsize",
                    "80",
                    "-fill",
                    "white",
                    "-gravity",
                    "south",
                    "-annotate",
                    "+0+50",
                    show_name,
                    poster_path,
                ],
                check=True,
            )
            if job:
                job.update(progress=60, message="Created show poster")
        season_frames_dir = os.path.join(app.temp_dir, "season_frames")
        os.makedirs(season_frames_dir, exist_ok=True)
        for i, episode in enumerate(episodes[:6]):
            frame_file = os.path.join(season_frames_dir, f"frame_{i:03d}.jpg")
            run_subprocess(
                [
                    "ffmpeg",
                    "-i",
                    str(episode),
                    "-vf",
                    "thumbnail",
                    "-frames:v",
                    "1",
                    frame_file,
                ],
                check=True,
                capture_output=True,
            )
        season_frames = list(Path(season_frames_dir).glob("*.jpg"))
        if season_frames:
            montage_args = [
                "montage",
                "-geometry",
                "400x225+5+5",
                "-background",
                "black",
                "-tile",
                "3x2",
                *[str(f) for f in season_frames],
                "-",
            ]
            convert_args = [
                "convert",
                "-",
                "-resize",
                "1000x1500",
                "-",
                "-gravity",
                "south",
                "-background",
                "#00000080",
                "-splice",
                "0x60",
                "-pointsize",
                "48",
                "-fill",
                "white",
                "-annotate",
                "+0+20",
                f"Season {season_num}",
                f"{folder}/season{season_num}-poster.jpg",
            ]
            p1 = subprocess.Popen(montage_args, stdout=subprocess.PIPE)
            p2 = subprocess.Popen(convert_args, stdin=p1.stdout)
            p2.communicate()
            run_subprocess(
                [
                    "convert",
                    f"{folder}/season{season_num}-poster.jpg",
                    "-resize",
                    "1000x562!",
                    f"{folder}/season{season_num}.jpg",
                ],
                check=True,
            )
            if job:
                job.update(progress=100, message="Created season artwork")
        for i, video in enumerate(episodes):
            video_base = str(video).rsplit(".", 1)[0]
            basename = os.path.basename(video_base)
            if app.config.get("clean_filenames", True):
                basename = clean_filename(basename)
            thumb_path = os.path.join(
                os.path.dirname(video_base), f"{basename}-thumb.jpg"
            )
            try:
                subprocess.run(
                    [
                        "ffmpeg",
                        "-ss",
                        "00:01:30",
                        "-i",
                        str(video),
                        "-vframes",
                        "1",
                        "-q:v",
                        "2",
                        thumb_path,
                    ],
                    check=True,
                    capture_output=True,
                )
                logger.info(f"Generated thumbnail: {thumb_path}")
            except subprocess.CalledProcessError:
                logger.error(f"Failed to generate thumbnail for {video}")
                if job:
                    job.update(
                        message=(
                            "Failed to generate thumbnail for "
                            f"{os.path.basename(str(video))}"
                        )
                    )
    except (subprocess.CalledProcessError, OSError) as e:
        logger.error(f"Error generating artwork: {e}")
        if job:
            job.update(message=f"Error generating artwork: {str(e)}")


def create_nfo_files(
    app, folder: str, show_name: str, season_num: str, job_id: str
) -> None:
    job = app.jobs.get(job_id)
    if job:
        job.update(status="creating_nfo", message="Creating NFO files")
    show_folder = str(Path(folder).parent)
    season_nfo = (
        "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>\n"
        "<season>\n"
        f"  <seasonnumber>{season_num}</seasonnumber>\n"
        f"  <title>Season {season_num}</title>\n"
        f"  <plot>Season {season_num} of {show_name}</plot>\n"
        "</season>\n"
    )
    with open(f"{folder}/season.nfo", "w") as f:
        f.write(season_nfo)
    tvshow_nfo = (
        "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>\n"
        "<tvshow>\n"
        f"  <title>{show_name}</title>\n"
        "  <studio>YouTube</studio>\n"
        "</tvshow>\n"
    )
    with open(f"{show_folder}/tvshow.nfo", "w") as f:
        f.write(tvshow_nfo)
    if job:
        job.update(progress=100, message="Created NFO files")


def list_media(app) -> List[Dict]:
    media = []
    output_dir = Path(app.config["output_dir"])
    if not output_dir.exists():
        return media
    for show_dir in output_dir.iterdir():
        if not show_dir.is_dir():
            continue
        show = {
            "name": show_dir.name,
            "path": str(show_dir),
            "seasons": [],
        }

        poster_file = show_dir / "poster.jpg"
        if poster_file.exists():
            show["poster"] = os.path.relpath(poster_file, output_dir)

        episode_total = 0

        for season_dir in show_dir.iterdir():
            if not season_dir.is_dir() or not season_dir.name.startswith("Season "):
                continue
            season = {
                "name": season_dir.name,
                "path": str(season_dir),
                "episodes": [],
            }

            match = re.search(r"(\d+)", season_dir.name)
            season_num = match.group(1) if match else ""

            season_poster = season_dir / f"season{season_num}-poster.jpg"
            if season_poster.exists():
                season["poster"] = os.path.relpath(season_poster, output_dir)
            for episode_file in season_dir.glob("*.mp4"):
                match = re.search(r"S(\d+)E(\d+)", episode_file.name)
                episode_num = int(match.group(2)) if match else None
                episode = {
                    "name": episode_file.stem,
                    "path": str(episode_file),
                    "size": episode_file.stat().st_size,
                    "modified": datetime.fromtimestamp(
                        episode_file.stat().st_mtime
                    ).strftime("%Y-%m-%d %H:%M:%S"),
                    "episode_num": episode_num,
                }
                season["episodes"].append(episode)
                episode_total += 1

            def sort_key(e):
                ep_num = e.get("episode_num")
                return (ep_num is None, ep_num if ep_num is not None else e["name"])

            season["episodes"].sort(key=sort_key)
            show["seasons"].append(season)
        show["seasons"].sort(key=lambda s: s["name"])
        show["episode_count"] = episode_total
        media.append(show)
    return media


def list_movies(app) -> List[Dict]:
    movies = []
    output_dir = Path(app.config["output_dir"])
    if not output_dir.exists():
        return movies
    for movie_dir in output_dir.iterdir():
        if not movie_dir.is_dir():
            continue
        if any(sd.is_dir() and sd.name.startswith("Season ") for sd in movie_dir.iterdir()):
            continue
        movie_file = None
        for ext in ["mp4"]:
            candidate = movie_dir / f"{movie_dir.name}.{ext}"
            if candidate.exists():
                movie_file = candidate
                break
        if movie_file:
            movies.append(
                {
                    "name": movie_dir.name,
                    "path": str(movie_file),
                    "size": movie_file.stat().st_size,
                    "modified": datetime.fromtimestamp(movie_file.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
    return movies


def get_playlist_videos(app, url: str) -> List[Dict]:
    try:
        result = subprocess.run(
            [
                app.config["ytdlp_path"],
                "--flat-playlist",
                "--dump-single-json",
                url,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(result.stdout)
        entries = data.get("entries", [])
        videos = []
        for idx, entry in enumerate(entries, start=1):
            videos.append(
                {"index": idx, "id": entry.get("id"), "title": entry.get("title")}
            )
        return videos
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        logger.error(f"Failed to fetch playlist info: {e}")
        return []


__all__ = [
    "create_folder_structure",
    "create_movie_folder",
    "download_playlist",
    "process_metadata",
    "process_movie_metadata",
    "convert_video_files",
    "generate_movie_artwork",
    "generate_artwork",
    "create_nfo_files",
    "list_media",
    "list_movies",
    "get_playlist_videos",
]
