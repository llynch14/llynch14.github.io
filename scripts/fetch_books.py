"""Fetch read books from Goodreads RSS and write data/books.json + data/reading_stats.json.

Pattern adapted from ChristopherJohnDillon/christopherjohndillon.github.io.
Stdlib only.
"""
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime
from pathlib import Path

FEED_URL = "https://www.goodreads.com/review/list_rss/70728365?shelf=read&per_page=200"
DATA = Path(__file__).resolve().parent.parent / "data"
OUT = DATA / "books.json"
STATS_OUT = DATA / "reading_stats.json"
N_BOOKS = 5
MIN_YEAR = 2020  # per-year chart cutoff; earlier reads still count in totals


def clean(text):
    return (text or "").strip()


def parse_date(raw):
    """Extract YYYY-MM-DD from a Goodreads date string."""
    m = re.search(r"(\d{4})/(\d{2})/(\d{2})", raw or "")
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"(\d{1,2}) (\w{3}) (\d{4})", raw or "")
    if m:
        dt = datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%d %b %Y")
        return dt.strftime("%Y-%m-%d")
    return ""


def fetch_feed(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return ET.fromstring(resp.read())


def all_items():
    """Fetch every page of the shelf feed (Goodreads paginates)."""
    items = []
    page = 1
    while True:
        root = fetch_feed(f"{FEED_URL}&page={page}")
        page_items = root.findall(".//item")
        if not page_items:
            break
        items.extend(page_items)
        if len(page_items) < 100:
            break
        page += 1
    return items


def parse_item(item):
    title = clean(item.findtext("title", ""))
    title = re.sub(r"\s*\(.+?\)\s*$", "", title)
    pages_el = item.find(".//book/num_pages")
    pages = int(pages_el.text) if pages_el is not None and pages_el.text and pages_el.text != "0" else 0
    book_id = clean(item.findtext("book_id", ""))
    return {
        "title": title,
        "author": clean(item.findtext("author_name", "")),
        "rating": int(item.findtext("user_rating", "0") or "0"),
        "read_at": parse_date(clean(item.findtext("user_read_at", ""))),
        "pages": pages,
        "cover": clean(item.findtext("book_large_image_url", "")) or clean(item.findtext("book_image_url", "")),
        "url": f"https://www.goodreads.com/book/show/{book_id}" if book_id else "",
    }


def build(books):
    dated = [b for b in books if b["read_at"]]
    dated.sort(key=lambda b: b["read_at"], reverse=True)
    recent = [
        {k: b[k] for k in ("title", "author", "rating", "read_at", "url")}
        for b in dated[:N_BOOKS]
    ]

    years = Counter(y for b in dated if (y := int(b["read_at"][:4])) >= MIN_YEAR)
    per_year = [{"year": y, "count": years[y]} for y in sorted(years)]

    timeline = [
        {k: b[k] for k in ("title", "author", "pages", "read_at", "cover")}
        for b in dated if b["pages"] > 0
    ]
    timeline.sort(key=lambda b: b["read_at"])

    sized = sorted((b for b in books if b["pages"] >= 100), key=lambda b: b["pages"])
    total_pages = sum(b["pages"] for b in sized)
    fun = {
        "total_books": len(sized),
        "total_pages": total_pages,
        "avg_pages": total_pages // len(sized) if sized else 0,
        "shortest": {"title": sized[0]["title"], "pages": sized[0]["pages"]} if sized else None,
        "longest": {"title": sized[-1]["title"], "pages": sized[-1]["pages"]} if sized else None,
    }
    return recent, per_year, fun, timeline


if __name__ == "__main__":
    books = [parse_item(it) for it in all_items()]
    recent, per_year, fun, timeline = build(books)
    DATA.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(recent, indent=2) + "\n")
    STATS_OUT.write_text(json.dumps({"per_year": per_year, "fun": fun, "timeline": timeline}, indent=2) + "\n")
    print(f"Parsed {len(books)} shelf items")
    print(f"Wrote {len(recent)} books to {OUT}")
    print(f"Wrote stats ({len(timeline)} timeline entries) to {STATS_OUT}")
