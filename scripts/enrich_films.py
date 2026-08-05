"""Enrich watched films with TMDB credits (director + top cast).

Auth: TMDB_KEY env var — a TMDB API Read Access Token (v4), stored as a
GitHub Actions secret. Results are cached in data/film_credits.json keyed
by "title|year", so each daily run only looks up films not seen before.
Stdlib only.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
STATS = DATA / "watching_stats.json"
CREDITS = DATA / "film_credits.json"
N_CAST = 8


def api(path, params, token):
    url = f"https://api.themoviedb.org/3/{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}", "accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def film_key(title, year):
    return f"{str(title or '').strip().lower()}|{year or ''}"


def lookup(title, year, token):
    params = {"query": title}
    if year:
        params["year"] = year
    results = api("search/movie", params, token).get("results") or []
    if not results and year:  # retry without the year constraint
        results = api("search/movie", {"query": title}, token).get("results") or []
    if not results:
        return None
    movie = results[0]
    credits = api(f"movie/{movie['id']}/credits", {}, token)
    directors = [c["name"] for c in credits.get("crew", []) if c.get("job") == "Director"]
    cast = [c["name"] for c in (credits.get("cast") or [])[:N_CAST]]
    return {"tmdb_id": movie["id"], "directors": directors, "cast": cast}


def main():
    token = os.environ.get("TMDB_KEY", "").strip()
    if not token:
        print("TMDB_KEY env var not set")
        return 1

    timeline = json.loads(STATS.read_text()).get("timeline", [])
    cache = {}
    if CREDITS.exists():
        try:
            cache = json.loads(CREDITS.read_text())
        except (ValueError, OSError):
            cache = {}

    new = 0
    for e in timeline:
        key = film_key(e.get("title"), e.get("year"))
        if key in cache:
            continue
        try:
            found = lookup(e.get("title"), e.get("year"), token)
        except Exception as err:
            print(f"  {e.get('title')}: {err}")
            continue
        cache[key] = found or {"tmdb_id": None, "directors": [], "cast": []}
        new += 1
        if not found:
            print(f"  no TMDB match: {e.get('title')} ({e.get('year')})")
        time.sleep(0.05)  # stay well under TMDB rate limits

    CREDITS.write_text(json.dumps(cache, indent=2) + "\n")
    print(f"Looked up {new} new films; cache holds {len(cache)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
