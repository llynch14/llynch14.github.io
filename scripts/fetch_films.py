"""Fetch watched films from Letterboxd RSS and accumulate them.

Letterboxd's RSS only exposes the ~50 most-recent diary entries, so each run
merges the current window into data/films_archive.json (keyed by guid).
Stats union that growing archive with data/letterboxd_baseline.json, the
all-time snapshot from a full account export (import_letterboxd_export.py).

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
BASELINE = DATA / "letterboxd_baseline.json"  # from import_letterboxd_export.py
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


def film_key(name, year):
    return f"{str(name or '').strip().lower()}|{str(year or '').strip()}"


def load_baseline():
    if BASELINE.exists():
        try:
            return json.loads(BASELINE.read_text())
        except (ValueError, OSError):
            pass
    return {"watched": [], "ratings": [], "diary": []}


def watching_stats(archive, baseline):
    dated = [e for e in archive if e.get("title") and re.match(r"\d{4}", e.get("watched_at") or "")]

    # films watched per year: baseline diary + RSS entries not already in it
    years = Counter()
    diary_seen = set()
    for d in baseline["diary"]:
        years[int(d["watched_at"][:4])] += 1
        diary_seen.add((d["key"], d["watched_at"]))
    for e in dated:
        if (film_key(e["title"], e.get("year")), e["watched_at"]) not in diary_seen:
            years[int(e["watched_at"][:4])] += 1
    per_year = [{"year": y, "count": years[y]} for y in sorted(years)]

    # one current rating per film: export snapshot, RSS entries override (newer)
    by_film = {}
    for r in baseline["ratings"]:
        by_film[r["key"]] = {
            "title": r["title"], "year": r["year"], "rating": r["rating"],
            "watched_at": r["rated_at"], "poster": "",
        }
    for e in dated:
        if e.get("rating") is not None:
            by_film[film_key(e["title"], e.get("year"))] = {
                "title": e["title"], "year": e.get("year"), "rating": e["rating"],
                "watched_at": e["watched_at"], "poster": e.get("poster", ""),
            }
    timeline = sorted(by_film.values(), key=lambda x: x["watched_at"])

    total = set(baseline["watched"]) | {film_key(e["title"], e.get("year")) for e in dated}
    rated = [t["rating"] for t in timeline]
    highest = max(timeline, key=lambda x: x["rating"], default=None)
    fun = {
        "total_films": len(total),
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
    per_year, fun, timeline = watching_stats(archive, load_baseline())
    DATA.mkdir(exist_ok=True)
    ARCHIVE.write_text(json.dumps(archive, indent=2) + "\n")
    OUT.write_text(json.dumps(films, indent=2) + "\n")
    STATS_OUT.write_text(json.dumps({"per_year": per_year, "fun": fun, "timeline": timeline}, indent=2) + "\n")
    print(f"Archive now holds {len(archive)} diary entries")
    print(f"Wrote {len(films)} films to {OUT}")
    print(f"Wrote stats ({len(timeline)} timeline entries) to {STATS_OUT}")
