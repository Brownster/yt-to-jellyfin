# Roadmap

The following are planned improvements and tasks for Tubarr:

- Separate tracking season/episode position from playlist position so adding a single video to a season does not affect automatic playlist downloads.
- Display all downloaded episodes in the media library and show a drop-down in the playlist view listing episodes downloaded from that playlist.
- **Add missing MIT license**. The README references a license but none existed.
- Implement job cancellation/stop capability so background jobs can be aborted.
- Provide real-time progress updates using WebSockets or Server-Sent Events instead of polling.
- Refactor the large `app.py` by splitting logic into separate modules.
- Add a configurable limit on the number of concurrent jobs.
- Validate configuration values against a schema when loading.
- Package the application so it can be installed with `pip`.
- Increase test coverage for playlist update logic.
- Continue to improve the media library experience.
