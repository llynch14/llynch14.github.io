"""Enrich watched films with director + top cast from Wikidata (no API key needed).

For each film in the watching timeline: search Wikidata by title, pick the
candidate that is a film with a matching release year, then read director
(P57) and cast members (P161). Person names are batch-resolved and cached.
Results cache in data/film_credits.json keyed by "title|year", so daily
runs only look up films not seen before. Stdlib only.
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
DELAY = 2.5

FILM_TYPES = {  # instance-of values we accept as "a film"
    "Q11424",    # film
    "Q24869",    # feature film
    "Q506240",   # television film
    "Q202866",   # animated film
    "Q93204",    # documentary film
    "Q24862",    # short film
    "Q17517379", # animated short
    "Q20667187", # concert film
    "Q7130449",  # musical film? (harmless extras)
}

API = "https://www.wikidata.org/w/api.php"
UA = {"User-Agent": "lindseylynch.me stats bot (personal site; contact via github.com/llynch14)"}


def api(params):
    params = dict(params, format="json", maxlag=5)
    req = urllib.request.Request(f"{API}?{urllib.parse.urlencode(params)}", headers=UA)
    for attempt in range(10):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            time.sleep(min(120, int(e.headers.get("Retry-After") or 0) or (10 * (attempt + 1))))
            continue
        err = data.get("error", {})
        if err.get("code") in ("maxlag", "ratelimited"):  # soft refusal inside a 200
            time.sleep(min(120, max(float(err.get("lag", 0) or 0) + 1, 10 * (attempt + 1))))
            continue
        if err:
            raise RuntimeError(f"wikidata error: {err.get('code')}")
        return data
    raise RuntimeError("rate-limited after retries")


def claim_ids(entity, prop):
    out = []
    for c in entity.get("claims", {}).get(prop, []):
        v = c.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(v, dict) and v.get("id"):
            out.append(v["id"])
    return out


def claim_year(entity):
    for c in entity.get("claims", {}).get("P577", []):
        t = c.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("time", "")
        if len(t) >= 5 and t[1:5].isdigit():
            return int(t[1:5])
    return None


def film_key(title, year):
    return f"{str(title or '').strip().lower()}|{year or ''}"


def lookup(title, year):
    found = api({"action": "wbsearchentities", "search": title, "language": "en",
                 "type": "item", "limit": 7}).get("search", [])
    if not found:
        return None
    ids = [f["id"] for f in found]
    time.sleep(DELAY)
    entities = api({"action": "wbgetentities", "ids": "|".join(ids),
                    "props": "claims"}).get("entities", {})
    best = None
    for qid in ids:  # keep search ranking order
        ent = entities.get(qid) or {}
        if not set(claim_ids(ent, "P31")) & FILM_TYPES:
            continue
        ey = claim_year(ent)
        if year and ey and abs(ey - year) > 1:
            continue
        best = ent
        break
    if not best:
        return None
    return {"qid": best.get("id") or "", "directors_q": claim_ids(best, "P57"),
            "cast_q": claim_ids(best, "P161")[:N_CAST]}


def resolve_names(qids, name_cache):
    todo = [q for q in qids if q not in name_cache]
    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        ents = api({"action": "wbgetentities", "ids": "|".join(batch),
                    "props": "labels", "languages": "en"}).get("entities", {})
        for q, e in ents.items():
            name_cache[q] = e.get("labels", {}).get("en", {}).get("value", "")
        time.sleep(DELAY)


def main(limit=None):
    timeline = json.loads(STATS.read_text()).get("timeline", [])
    cache = {}
    if CREDITS.exists():
        try:
            cache = json.loads(CREDITS.read_text())
        except (ValueError, OSError):
            cache = {}

    pending = [e for e in timeline if film_key(e.get("title"), e.get("year")) not in cache]
    if limit:
        pending = pending[:limit]

    name_cache, new, missed = {}, 0, 0
    for e in pending:
        key = film_key(e.get("title"), e.get("year"))
        try:
            r = lookup(e.get("title"), e.get("year"))
            if r:
                resolve_names(r["directors_q"] + r["cast_q"], name_cache)
        except Exception as err:
            print(f"  stopping at {e.get('title')}: {err} (progress saved; rerun to resume)", flush=True)
            break
        if not r:
            missed += 1
            print(f"  no match: {e.get('title')} ({e.get('year')})", flush=True)
            cache[key] = {"qid": None, "directors": [], "cast": []}
        else:
            cache[key] = {
                "qid": r["qid"],
                "directors": [name_cache.get(q, "") for q in r["directors_q"] if name_cache.get(q)],
                "cast": [name_cache.get(q, "") for q in r["cast_q"] if name_cache.get(q)],
            }
        new += 1
        if new % 10 == 0:
            CREDITS.write_text(json.dumps(cache, indent=2) + "\n")
            print(f"  ...{new}/{len(pending)}", flush=True)
        time.sleep(DELAY)

    CREDITS.write_text(json.dumps(cache, indent=2) + "\n")
    print(f"Looked up {new} films ({missed} unmatched); cache holds {len(cache)}")
    return 0


if __name__ == "__main__":
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    sys.exit(main(lim))
