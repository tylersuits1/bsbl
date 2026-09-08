"""Headlines from Google News and Bing News, both of which publish a
plain RSS search feed with no registration required — no undocumented
internal API, no scraping restrictions to work around. Mirrors
web_news_service.dart in the Flutter sibling app. Google's and Bing's
terms restrict these feeds to personal, non-commercial use in a feed
reader — exactly this app's use case.

Both are best-effort: any parse failure on an item (or the whole feed)
is swallowed and yields an empty list, since a broken feed shouldn't
block the other one from still showing headlines.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from xml.etree import ElementTree

import httpx

from .models import Headline

_MONTH_ABBRS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]

_RFC822_RE = re.compile(r"(\d{1,2})\s+(\w{3})\s+(\d{4})\s+(\d{2}):(\d{2}):(\d{2})")


def _parse_rfc822(value: str) -> datetime | None:
    """RSS's date format, e.g. 'Sat, 29 Aug 2026 00:13:07 GMT' — not
    handled by datetime.fromisoformat, which expects ISO 8601.
    """
    match = _RFC822_RE.search(value)
    if not match:
        return None
    day, month_abbr, year, hour, minute, second = match.groups()
    try:
        month = _MONTH_ABBRS.index(month_abbr) + 1
    except ValueError:
        return None
    return datetime(int(year), month, int(day), int(hour), int(minute), int(second), tzinfo=timezone.utc)


def _time_ago(published_at: datetime) -> str:
    diff = datetime.now(timezone.utc) - published_at.astimezone(timezone.utc)
    minutes = int(diff.total_seconds() // 60)
    if minutes < 60:
        return f"{minutes} mins ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hrs ago"
    return f"{hours // 24} days ago"


async def fetch_google_news(client: httpx.AsyncClient, query: str) -> list[Headline]:
    params = {"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"}
    url = f"https://news.google.com/rss/search?{urlencode(params)}"
    return await _fetch_rss(client, url, source="google")


async def fetch_bing_news(client: httpx.AsyncClient, query: str) -> list[Headline]:
    params = {"q": query, "format": "RSS"}
    url = f"https://www.bing.com/news/search?{urlencode(params)}"
    return await _fetch_rss(client, url, source="bing")


async def _fetch_rss(client: httpx.AsyncClient, url: str, *, source: str) -> list[Headline]:
    try:
        response = await client.get(url, timeout=10.0)
        if response.status_code != 200:
            return []
        root = ElementTree.fromstring(response.content)
        headlines = []
        for item in root.iter("item"):
            headline = _parse_google_item(item) if source == "google" else _parse_bing_item(item)
            if headline:
                headlines.append(headline)
        return headlines
    except Exception:
        return []


def _text_of(item, tag: str) -> str | None:
    el = item.find(tag)
    return el.text.strip() if el is not None and el.text else None


def _parse_google_item(item) -> Headline | None:
    try:
        title = _text_of(item, "title") or ""
        link = _text_of(item, "link") or ""
        pub_date = _text_of(item, "pubDate")
        published_at = _parse_rfc822(pub_date) if pub_date else None
        source_name = _text_of(item, "source") or "Google News"
        if not title or not link or not published_at:
            return None

        # Google's titles are formatted "Headline - Source" — drop the
        # trailing source since it's shown separately as the byline.
        suffix = f" - {source_name}"
        if title.endswith(suffix):
            title = title[: -len(suffix)]

        return Headline(title=title, byline=source_name, time_ago=_time_ago(published_at), url=link, published_at=published_at)
    except Exception:
        return None


def _parse_bing_item(item) -> Headline | None:
    try:
        title = _text_of(item, "title") or ""
        link = _text_of(item, "link") or ""
        pub_date = _text_of(item, "pubDate")
        published_at = _parse_rfc822(pub_date) if pub_date else None
        if not title or not link or not published_at:
            return None

        source_name = None
        for child in item:
            if child.tag.endswith("Source"):
                source_name = (child.text or "").strip()
                break

        return Headline(
            title=title,
            byline=source_name or "Bing News",
            time_ago=_time_ago(published_at),
            url=link,
            published_at=published_at,
        )
    except Exception:
        return None


def merge_headlines(sources: list[list[Headline]]) -> list[Headline]:
    """Merges headlines from multiple sources into one newest-first list:
    anything older than a week is dropped (a story stays visible for up
    to a week if nothing newer has bumped it), duplicates of the same
    story across sources are collapsed by title.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    by_title: dict[str, Headline] = {}
    for headlines in sources:
        for headline in headlines:
            if headline.published_at.astimezone(timezone.utc) < cutoff:
                continue
            key = headline.title.strip().lower()
            if not key:
                continue
            existing = by_title.get(key)
            if existing is None or headline.published_at > existing.published_at:
                by_title[key] = headline

    return sorted(by_title.values(), key=lambda h: h.published_at, reverse=True)
