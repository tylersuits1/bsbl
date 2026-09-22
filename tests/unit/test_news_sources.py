from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest

from bsbl.models import Headline
from bsbl.news_sources import (
    _parse_bing_item,
    _parse_google_item,
    _parse_rfc822,
    _time_ago,
    fetch_bing_news,
    fetch_google_news,
    merge_headlines,
)
from xml.etree import ElementTree

_GOOGLE_RSS = """<?xml version="1.0"?>
<rss><channel>
  <item>
    <title>Braves win 5-2 - The Athletic</title>
    <link>https://example.com/braves-win</link>
    <pubDate>Sat, 29 Aug 2026 20:13:07 GMT</pubDate>
    <source>The Athletic</source>
  </item>
  <item>
    <title>Missing fields</title>
  </item>
</channel></rss>"""

_BING_RSS = """<?xml version="1.0"?>
<rss xmlns:News="https://www.bing.com/news">
  <channel>
    <item>
      <title>Braves clinch division</title>
      <link>https://example.com/clinch</link>
      <pubDate>Sat, 29 Aug 2026 18:00:00 GMT</pubDate>
      <News:Source>NBC Sports</News:Source>
    </item>
  </channel>
</rss>"""


def test_parse_rfc822_valid():
    dt = _parse_rfc822("Sat, 29 Aug 2026 00:13:07 GMT")
    assert dt == datetime(2026, 8, 29, 0, 13, 7, tzinfo=timezone.utc)


def test_parse_rfc822_invalid_returns_none():
    assert _parse_rfc822("not a date") is None
    assert _parse_rfc822("") is None


@pytest.mark.parametrize(
    "minutes_ago, expected",
    [
        (5, "5 mins ago"),
        (59, "59 mins ago"),
        (60, "1 hrs ago"),
        (90, "1 hrs ago"),
        (23 * 60, "23 hrs ago"),
        (25 * 60, "1 days ago"),
        (3 * 24 * 60, "3 days ago"),
    ],
)
def test_time_ago(minutes_ago, expected):
    published = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    assert _time_ago(published) == expected


def test_parse_google_item_strips_source_suffix():
    root = ElementTree.fromstring(_GOOGLE_RSS)
    items = list(root.iter("item"))

    headline = _parse_google_item(items[0])
    assert headline is not None
    assert headline.title == "Braves win 5-2"  # " - The Athletic" stripped
    assert headline.byline == "The Athletic"
    assert headline.url == "https://example.com/braves-win"

    # missing link/pubDate -> None, doesn't raise
    assert _parse_google_item(items[1]) is None


def test_parse_bing_item_reads_namespaced_source():
    root = ElementTree.fromstring(_BING_RSS)
    item = next(root.iter("item"))
    headline = _parse_bing_item(item)
    assert headline is not None
    assert headline.title == "Braves clinch division"
    assert headline.byline == "NBC Sports"


def test_merge_headlines_dedupes_by_title_keeping_newest():
    now = datetime.now(timezone.utc)
    old = Headline(
        title="Braves Win", byline="A", time_ago="", url="https://a",
        published_at=now - timedelta(hours=2),
    )
    newer = Headline(
        title="braves win", byline="B", time_ago="", url="https://b",  # same title, different case
        published_at=now - timedelta(hours=1),
    )
    merged = merge_headlines([[old], [newer]])
    assert len(merged) == 1
    assert merged[0].url == "https://b"


def test_merge_headlines_drops_anything_older_than_a_week():
    stale = Headline(
        title="Old news", byline="", time_ago="", url="https://a",
        published_at=datetime.now(timezone.utc) - timedelta(days=8),
    )
    fresh = Headline(
        title="Fresh news", byline="", time_ago="", url="https://b",
        published_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    merged = merge_headlines([[stale, fresh]])
    assert [h.title for h in merged] == ["Fresh news"]


def test_merge_headlines_sorted_newest_first():
    now = datetime.now(timezone.utc)
    a = Headline(title="A", byline="", time_ago="", url="a", published_at=now - timedelta(hours=3))
    b = Headline(title="B", byline="", time_ago="", url="b", published_at=now - timedelta(hours=1))
    c = Headline(title="C", byline="", time_ago="", url="c", published_at=now - timedelta(hours=2))
    merged = merge_headlines([[a, b, c]])
    assert [h.title for h in merged] == ["B", "C", "A"]


def test_merge_headlines_empty_input():
    assert merge_headlines([]) == []
    assert merge_headlines([[]]) == []


@pytest.mark.asyncio
async def test_fetch_google_news_parses_response():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "news.google.com" in str(request.url)
        return httpx.Response(200, content=_GOOGLE_RSS)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        headlines = await fetch_google_news(client, "Atlanta Braves MLB")
    assert len(headlines) == 1
    assert headlines[0].title == "Braves win 5-2"


@pytest.mark.asyncio
async def test_fetch_bing_news_parses_response():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "bing.com" in str(request.url)
        return httpx.Response(200, content=_BING_RSS)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        headlines = await fetch_bing_news(client, "Atlanta Braves MLB")
    assert len(headlines) == 1
    assert headlines[0].byline == "NBC Sports"


@pytest.mark.asyncio
async def test_fetch_google_news_non_200_returns_empty():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        headlines = await fetch_google_news(client, "query")
    assert headlines == []


@pytest.mark.asyncio
async def test_fetch_google_news_malformed_xml_returns_empty():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not xml at all <<<")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        headlines = await fetch_google_news(client, "query")
    assert headlines == []
