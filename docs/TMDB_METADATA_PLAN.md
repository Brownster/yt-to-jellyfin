# TMDB Movie Metadata Integration Plan

This document outlines the planned work to enhance movie downloads with metadata and posters from [The Movie Database](https://www.themoviedb.org/).

## Overview

When a user provides a TMDB API key, Tubarr should automatically query TMDB for matching movie details. If a reliable match is found the movie poster and rich metadata will be used to generate the Jellyfin `movie.nfo`. If the movie cannot be confidently identified or no API key is set, the existing YouTube based metadata generation will be used.

## Implementation Steps

1. **Configuration**
   - Add `tmdb_api_key` to `ConfigModel` in `tubarr/config.py`.
   - Load the value from the environment variable `TMDB_API_KEY` and from `config/config.yml` under a new optional `tmdb` section.
   - Expose the setting through the `/config` API and the web settings page.

2. **TMDB Helper Module**
   - Create `tubarr/tmdb.py` with helper functions:
     - `clean_title()` – removes resolution, year brackets and other common YouTube suffixes.
     - `search_movie(title, year, api_key)` – calls `https://api.themoviedb.org/3/search/movie`.
     - `fetch_movie_details(movie_id, api_key)` – calls `https://api.themoviedb.org/3/movie/<id>?append_to_response=credits`.
     - `download_poster(path, dest, api_key)` – retrieves the poster image.
     - Include simple fuzzy matching (e.g. with `difflib.SequenceMatcher`) to select the best result.

3. **Metadata Processing**
   - Update `process_movie_metadata` in `tubarr/media.py`:
     - Extract the probable title and year from the YouTube metadata.
     - If `tmdb_api_key` is present, call `search_movie` and fetch details.
     - When a match confidence exceeds a threshold, rename the file and build `movie.nfo` using TMDB data (title, plot, genres, cast, year, tmdb id).
     - Save the downloaded poster as `poster.jpg` in the movie folder.
     - Fall back to the current behaviour when the key is missing or no reliable match is found.

4. **Tests**
   - Extend `tests/test_movie.py` to mock TMDB HTTP calls and verify that:
     - Metadata fields in `movie.nfo` originate from TMDB when the key is configured.
     - Posters are downloaded to the correct location.
     - The existing YouTube-based path is used when TMDB lookup fails.
   - Add validation tests in `tests/test_config_validation.py` for the new setting.

5. **Documentation Updates**
   - Document the new environment variable and configuration option in `README.md`.
   - Mention the optional TMDB feature in the feature list and usage sections.
   - Update `roadmap.md` to reflect the planned integration.

## Notes

TMDB allows up to 40 requests every 10 seconds on free accounts, which is sufficient for individual movie downloads. Users must obtain a free API key from their TMDB account settings.

