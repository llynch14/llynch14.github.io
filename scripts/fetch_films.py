"""Fetch watched films from Letterboxd RSS and accumulate them.

Letterboxd's RSS only exposes the ~50 most-recent diary entries, so each run
merges the current window into data/films_archive.json (keyed by guid) and
stats are computed from that growing archive.

Pattern adapted from ChristopherJohnDillon/christopherjohndillon.github.io.
Stdlib only.
"""
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

FEED_URL = "https://letterboxd.com/whiteth0rn/rss/"
DATA = Path(__file__).resolve().parent.parent / "data"
OUT = DATA / "films.json"
STATS_OUT = DATA / "watching_stats.json"
ARCHIVE = DATA / "films_archive.json"
NS = {"letterboxd": "https://letterboxd.com", "tmdb": "https://themoviedb.org"}
N_FILMS = 5
ENTRY_KEYS = ("title", "year", "rating", "watched_at", "poster", "url")


def clean(text):
    return (text or "").strip()


def poster_from_description(desc):
    m = re.search(r'<img src="([^"]+)"', desc or "")
    return m.group(1) if m else ""


def parse_item(item):
    year_raw = clean(item.findtext("letterboxd:filmYear", "", NS))
    rating_raw = clean(item.findtext("letterboxd:memberRating", "", NS))
    url = clean(item.findtext("link", ""))
    watched_at = clean(item.findtext("letterboxd:watchedDate", "", NS))
    guid = clean(item.findtext("guid", "")) or (url + "#" + watched_at)
    return {
        "guid": guid,
        "title": clean(item.findtext("letterboxd:filmTitle", "", NS)),
        "year": int(year_raw) if year_raw.isdigit() else None,
        "rating": float(rating_raw) if rating_raw else None,
        "watched_at": watched_at,
        "poster": poster_from_description(item.findtext("description", "")),
        "url": url,
    }


def load_archive():
    if ARCHIVE.exists():
        try:
            data = json.loads(ARCHIVE.read_text())
            return data if isinstance(data, list) else []
        except (ValueError, OSError):
            return []
    return []


def merge_archive(archive, new_entries):
    """Merge by guid; newer entries win, old ones are never dropped."""
    by_guid = {e["guid"]: e for e in archive if e.get("guid")}
    for e in new_entries:
        if e.get("guid"):
            by_guid[e["guid"]] = e
    merged = list(by_guid.values())
    merged.sort(key=lambda e: e.get("watched_at") or "")
    return merged


def recent_films(archive, n=N_FILMS):
    valid = [e for e in archive if e.get("title") and e.get("watched_at")]
    valid.sort(key=lambda e: e["watched_at"], reverse=True)
    return [{k: e.get(k) for k in ENTRY_KEYS} for e in valid[:n]]


def watching_stats(archive):
    years = Counter()
    timeline = []
    rated = []
    for e in archive:
        m = re.match(r"(\d{4})", e.get("watched_at") or "")
        if not m:
            continue
        years[int(m.group(1))] += 1
        if e.get("rating") is not None:
            timeline.append({
                "title": e["title"],
                "year": e.get("year"),
                "rating": e["rating"],
                "watched_at": e["watched_at"],
                "poster": e.get("poster", ""),
            })
            rated.append(e["rating"])
    per_year = [{"year": y, "count": years[y]} for y in sorted(years)]
    timeline.sort(key=lambda x: x["watched_at"])
    highest = max(timeline, key=lambda x: x["rating"], default=None)
    fun = {
        "total_films": sum(years.values()),
        "avg_rating": round(sum(rated) / len(rated), 2) if rated else 0.0,
        "highest_rated": {"title": highest["title"], "rating": highest["rating"]} if highest else None,
    }
    return per_year, fun, timeline


def fetch_feed():
    req = urllib.request.Request(FEED_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return ET.fromstring(resp.read())


if __name__ == "__main__":
    root = fetch_feed()
    items = root.findall(".//item")
    archive = merge_archive(load_archive(), [parse_item(it) for it in items])
    films = recent_films(archive)
    per_year, fun, timeline = watching_stats(archive)
    DATA.mkdir(exist_ok=True)
    ARCHIVE.write_text(json.dumps(archive, indent=2) + "\n")
    OUT.write_text(json.dumps(films, indent=2) + "\n")
    STATS_OUT.write_text(json.dumps({"per_year": per_year, "fun": fun, "timeline": timeline}, indent=2) + "\n")
    print(f"Archive now holds {len(archive)} diary entries")
    print(f"Wrote {len(films)} films to {OUT}")
    print(f"Wrote stats ({len(timeline)} timeline entries) to {STATS_OUT}")
