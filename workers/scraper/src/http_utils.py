"""Shared HTTP helpers for pharmacy connectors."""
import asyncio
import re
from typing import Any, Awaitable, Callable, Iterable, TypeVar

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.IGNORECASE)

T = TypeVar("T")


def build_client(user_agent: str, base_headers: dict[str, str] | None = None) -> httpx.AsyncClient:
    """AsyncClient with sane defaults for Chilean storefronts."""
    headers = {
        "User-Agent": user_agent,
        "Accept-Language": "es-CL,es;q=0.9",
    }
    if base_headers:
        headers.update(base_headers)
    return httpx.AsyncClient(
        headers=headers,
        timeout=httpx.Timeout(30.0, connect=15.0),
        follow_redirects=True,
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    )


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def get_json(client: httpx.AsyncClient, url: str, **kwargs: Any) -> Any:
    response = await client.get(url, **kwargs)
    response.raise_for_status()
    return response.json()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def get_text(client: httpx.AsyncClient, url: str, **kwargs: Any) -> str:
    response = await client.get(url, **kwargs)
    response.raise_for_status()
    return response.text


def extract_locs(xml: str) -> list[str]:
    """Pull <loc> values out of a sitemap or sitemap index."""
    return LOC_RE.findall(xml)


async def fetch_sitemap_urls(
    client: httpx.AsyncClient,
    sitemap_url: str,
    child_filter: Callable[[str], bool] | None = None,
) -> list[str]:
    """Resolve a sitemap index into the flat list of URLs it points at.

    `child_filter` selects which child sitemaps of an index are worth fetching
    (product sitemaps only, typically). Leaf sitemaps ignore it.
    """
    try:
        xml = await get_text(client, sitemap_url)
    except Exception as exc:
        logger.error(f"Sitemap fetch failed {sitemap_url}: {exc}")
        return []

    locs = extract_locs(xml)
    if "<sitemapindex" not in xml.lower():
        return locs

    urls: list[str] = []
    for child in locs:
        if child_filter and not child_filter(child):
            continue
        try:
            child_xml = await get_text(client, child)
        except Exception as exc:
            logger.error(f"Child sitemap failed {child}: {exc}")
            continue
        urls.extend(extract_locs(child_xml))
    return urls


async def gather_limited(
    items: Iterable[T],
    worker: Callable[[T], Awaitable[Any]],
    concurrency: int = 5,
) -> list[Any]:
    """Run `worker` over `items` with a hard concurrency cap.

    Exceptions are logged and become `None` so one bad product never kills a run.
    """
    semaphore = asyncio.Semaphore(concurrency)

    async def guarded(item: T) -> Any:
        async with semaphore:
            try:
                return await worker(item)
            except Exception as exc:
                logger.warning(f"Worker failed for {item!r}: {exc}")
                return None

    return await asyncio.gather(*(guarded(item) for item in items))
