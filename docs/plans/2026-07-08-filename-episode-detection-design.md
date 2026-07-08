# Filename Episode Detection

## Goal

Add an opt-in TV download mode that reads season and episode numbers from source titles such as `The Jerry Springer Show S24E28 - I Cheated With Three Strippers`. The existing sequential numbering and TVDB air-date detection modes remain available.

## User flow

The New TV Download form adds a **Detect season and episode from titles** toggle. When selected, Tubarr fetches the source item list before creating the job and parses each title. The season and episode inputs become optional because each item has its own values.

If every title contains a supported season and episode marker, Tubarr starts the job immediately. If any title cannot be parsed, a modal lists only those items. Each row requires a season and episode number. Tubarr creates no job until every unresolved item has a valid mapping.

The supplied TV Show Name remains authoritative. For a show name of `The Jerry Springer Show`, season 24, episode 28, and source episode title `I Cheated With Three Strippers`, Tubarr writes:

- Media filename: `The Jerry Springer Show S24E28 - I Cheated With Three Strippers.mp4`
- NFO title: `I Cheated With Three Strippers`
- NFO show title: `The Jerry Springer Show`

## Parsing and normalization

The parser accepts case-insensitive `S<number>E<number>` markers with optional spaces and common separators. It extracts the text after the marker as the episode title. It removes leading separators, emoji, control characters, and excess whitespace. If no useful episode title remains, it uses `Episode <number>`.

Manual mappings and detected mappings use a stable source identifier, falling back to playlist index when the provider supplies no identifier. The server validates positive season and episode integers, rejects duplicate mappings, and verifies that submitted mappings belong to the fetched source list.

## Processing

The job stores its per-item mappings. Metadata processing matches downloaded `.info.json` records to those mappings and creates season-specific directories, filenames, and NFO files. The download staging name may remain index-based because final names are assigned during metadata processing.

Filename detection does not call TVDB. The filename and TVDB toggles are mutually exclusive. Tracked updates repeat the same detection process for new source items; unrecognized new titles require manual resolution before an update job can start.

## Errors and tests

Preflight errors leave the form populated and show a specific message. Invalid manual values remain in the modal for correction. Backend validation protects API callers that bypass the browser.

Tests cover supported title variants, emoji removal, whitespace cleanup, missing titles, duplicates, mixed seasons, API validation, modal submission, mapper behavior, filenames, and NFO fields. Existing sequential and TVDB tests must continue to pass.
