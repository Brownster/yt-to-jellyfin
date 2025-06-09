import re
import requests
from difflib import SequenceMatcher
from typing import Dict, Optional

BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE = "https://image.tmdb.org/t/p/w500"


def clean_title(title: str) -> str:
    """Remove common YouTube style suffixes from titles."""
    if not title:
        return ""
    title = re.sub(r"\[[^\]]*\]", "", title)
    title = re.sub(r"\((?:\d{4}p|HD|4K).*?\)", "", title, flags=re.I)
    title = re.sub(r"\b\d{3,4}p\b", "", title, flags=re.I)
    return re.sub(r"\s+", " ", title).strip()


def search_movie(title: str, year: str, api_key: str) -> Optional[Dict]:
    params = {"api_key": api_key, "query": title}
    if year:
        params["year"] = year
    resp = requests.get(f"{BASE_URL}/search/movie", params=params, timeout=10)
    resp.raise_for_status()
    results = resp.json().get("results", [])
    best = None
    best_ratio = 0.0
    for movie in results:
        ratio = SequenceMatcher(None, title.lower(), movie.get("title", "").lower()).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best = movie
    return best if best_ratio >= 0.5 else None


def fetch_movie_details(movie_id: int, api_key: str) -> Dict:
    params = {"api_key": api_key, "append_to_response": "credits"}
    resp = requests.get(f"{BASE_URL}/movie/{movie_id}", params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def download_poster(path: str, dest: str, api_key: str) -> None:
    if not path:
        return
    url = f"{IMAGE_BASE}{path}"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        f.write(resp.content)


__all__ = [
    "clean_title",
    "search_movie",
    "fetch_movie_details",
    "download_poster",
]
