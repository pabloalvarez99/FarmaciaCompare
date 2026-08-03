import pytest
from src.http_utils import extract_locs, gather_limited

SITEMAP_INDEX = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<sitemap><loc>https://www.cruzverde.cl/sitemap_0-product.xml</loc></sitemap>
<sitemap><loc>https://www.cruzverde.cl/sitemap_3-image.xml</loc></sitemap>
</sitemapindex>"""

SITEMAP_LEAF = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://www.cruzverde.cl/morelin/1006.html</loc><lastmod>2026-01-01</lastmod></url>
<url><loc>
  https://www.cruzverde.cl/sostac/1027.html
</loc></url>
</urlset>"""


def test_extract_locs_from_index():
    assert extract_locs(SITEMAP_INDEX) == [
        "https://www.cruzverde.cl/sitemap_0-product.xml",
        "https://www.cruzverde.cl/sitemap_3-image.xml",
    ]


def test_extract_locs_trims_whitespace():
    assert extract_locs(SITEMAP_LEAF) == [
        "https://www.cruzverde.cl/morelin/1006.html",
        "https://www.cruzverde.cl/sostac/1027.html",
    ]


def test_extract_locs_on_empty_document():
    assert extract_locs("<urlset></urlset>") == []


async def test_gather_limited_preserves_order():
    async def double(n):
        return n * 2

    assert await gather_limited(range(5), double, concurrency=2) == [0, 2, 4, 6, 8]


async def test_gather_limited_turns_failures_into_none():
    async def flaky(n):
        if n == 2:
            raise ValueError("boom")
        return n

    assert await gather_limited([1, 2, 3], flaky, concurrency=3) == [1, None, 3]


async def test_gather_limited_respects_concurrency_cap():
    import asyncio

    active = 0
    peak = 0

    async def tracked(n):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return n

    await gather_limited(range(10), tracked, concurrency=3)
    assert peak <= 3
