"""One-time import of a Letterboxd account export (Settings -> Data -> Export).

Writes data/letterboxd_baseline.json holding the full watched list, current
per-film ratings, and dated diary entries. fetch_films.py unions this baseline
with the rolling RSS archive, so stats cover all-time history rather than the
~50-entry RSS window.

Stdlib only. Usage: python scripts/import_letterboxd_export.py <export-dir>
"""
import csv
import json
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
OUT = DATA / "letterboxd_baseline.json"


def film_key(name, year):
    return f"{str(name or '').strip().lower()}|{str(year or '').strip()}"


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main(export_dir):
    exp = Path(export_dir)

    watched = sorted({film_key(r["Name"], r["Year"]) for r in read_csv(exp / "watched.csv")})

    ratings = []
    for r in read_csv(exp / "ratings.csv"):
        ratings.append({
            "key": film_key(r["Name"], r["Year"]),
            "title": r["Name"],
            "year": int(r["Year"]) if r["Year"].isdigit() else None,
            "rating": float(r["Rating"]),
            "rated_at": r["Date"],
        })

    diary = [
        {"key": film_key(r["Name"], r["Year"]), "watched_at": r["Watched Date"]}
        for r in read_csv(exp / "diary.csv")
        if r.get("Watched Date")
    ]

    DATA.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "watched": watched,
        "ratings": ratings,
        "diary": diary,
    }, indent=2) + "\n")
    print(f"Baseline: {len(watched)} watched films, {len(ratings)} ratings, {len(diary)} diary entries -> {OUT}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python scripts/import_letterboxd_export.py <export-dir>")
    main(sys.argv[1])
