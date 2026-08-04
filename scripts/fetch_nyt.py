"""Fetch NYT Games stats (Wordle + Connections if available) and write data/nyt_stats.json.

Auth: NYT_S env var — the NYT-S session cookie value (stored as a GitHub Actions
secret; never committed). Only aggregate stats are written to the public file.
Stdlib only.
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
OUT = DATA / "nyt_stats.json"

WORDLE_ENDPOINTS = [
    "https://www.nytimes.com/svc/games/state/wordleV2/latests",
    "https://www.nytimes.com/svc/games/state/wordle/latest",
]
CONNECTIONS_ENDPOINTS = [
    "https://www.nytimes.com/svc/games/state/connectionsV2/latests",
    "https://www.nytimes.com/svc/games/state/connections/latests",
    "https://www.nytimes.com/svc/games/state/connections/latest",
]


def fetch(url, cookie):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Cookie": f"NYT-S={cookie};",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  {url} -> {e}")
        return None


def find_stats_dict(obj, required):
    """Recursively find the first dict containing all `required` keys."""
    if isinstance(obj, dict):
        if all(k in obj for k in required):
            return obj
        for v in obj.values():
            found = find_stats_dict(v, required)
            if found:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = find_stats_dict(v, required)
            if found:
                return found
    return None


def main():
    cookie = os.environ.get("NYT_S", "").strip()
    if not cookie:
        print("NYT_S env var not set")
        return 1

    out = {}

    print("Wordle:")
    for url in WORDLE_ENDPOINTS:
        data = fetch(url, cookie)
        if not data:
            continue
        stats = find_stats_dict(data, ("gamesPlayed", "maxStreak"))
        if stats:
            games_played = stats.get("gamesPlayed", 0)
            games_won = stats.get("gamesWon", 0)
            out["wordle"] = {
                "games_played": games_played,
                "games_won": games_won,
                "win_pct": round(100 * games_won / games_played) if games_played else 0,
                "current_streak": stats.get("currentStreak", 0),
                "max_streak": stats.get("maxStreak", 0),
                "guesses": {k: v for k, v in (stats.get("guesses") or {}).items()},
            }
            print(f"  ok via {url}")
            break
        print(f"  {url}: response had no stats dict; top-level keys: {list(data)[:8]}")

    print("Connections:")
    for url in CONNECTIONS_ENDPOINTS:
        data = fetch(url, cookie)
        if not data:
            continue
        stats = find_stats_dict(data, ("currentStreak", "maxStreak")) or \
                find_stats_dict(data, ("puzzlesSolved",))
        if stats:
            out["connections"] = {
                k: v for k, v in stats.items()
                if isinstance(v, (int, float)) and not k.startswith("_")
            }
            print(f"  ok via {url}")
            break
        print(f"  {url}: response had no stats dict; top-level keys: {list(data)[:8]}")

    if "wordle" not in out:
        print("FAILED: no Wordle stats found (cookie expired or endpoints changed?)")
        return 1

    DATA.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
