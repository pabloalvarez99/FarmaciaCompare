"""Report how healthy `pharmacy_products.image_url` actually is, per chain.

Coverage alone lies. A row can have an image_url that 404s, points at a
placeholder, or is malformed — all of which read as "has an image" in a
`count(image_url)`. Farmex, for instance, sits at 99.8% coverage while roughly
5% of its Shopify URLs have been deleted upstream since the scrape.

This samples real URLs per chain and reports three separate things:

  coverage   — rows with a non-null image_url
  malformed  — stored values that are not a usable absolute http(s) URL
  reachable  — sampled URLs that actually return an image

    python -m src.check_images                  # 40 per chain
    python -m src.check_images --sample 150
    python -m src.check_images --chain farmex --fail-under 90

`--fail-under` exits non-zero when a chain's reachable rate drops below the
threshold, so this can gate a scheduled job instead of being read by hand.
"""
from __future__ import annotations

import argparse
import asyncio
import collections

import httpx
from loguru import logger
from sqlalchemy import text

from .base_scraper import BROWSER_USER_AGENTS
from .db import AsyncSessionLocal

# Deliberately a browser UA, unlike every scraper in this package.
#
# This is not scraping: we are asking whether an image asset the site already
# links to is reachable, which is exactly the request a visitor's browser makes.
# Measured against Dr. Simi's vteximg CDN on the same 8 URLs, sequential, 350 ms
# apart:
#     BOT UA    -> 429 x8   (with and without a Range header)
#     browser UA-> 200 x8
# So probing as the bot measured the CDN's UA policy, not the health of our
# data, and reported a chain that is actually 100% fine as 0% reachable.
ASSET_USER_AGENT = BROWSER_USER_AGENTS[0]

# Magic numbers beat Content-Type: a CDN can answer 200 with the right header
# and an empty or HTML body, which is exactly what a soft-404 looks like.
MAGIC_PREFIXES: dict[bytes, str] = {
    b"\xff\xd8\xff": "JPEG",
    b"\x89PNG": "PNG",
    b"RIFF": "WEBP",
    b"GIF8": "GIF",
    b"<svg": "SVG",
    b"<?xm": "SVG",
}

# Per-host, not global. Some CDNs (Dr. Simi's vteximg) start answering 429 at a
# dozen parallel requests, and a throttled probe says nothing about whether the
# image exists — the checker would just be measuring its own rudeness.
CONCURRENCY_PER_HOST = 2
MAX_429_RETRIES = 3

# Pause between consecutive requests to the same host. Dr. Simi's vteximg CDN
# 429s almost everything at 4-way concurrency with no pacing, which left the
# chain unmeasurable; 2-way plus this delay gets a clean read and is still
# polite. Costs a few seconds per chain, which is nothing for a health check.
PER_HOST_DELAY_S = 0.35


def identify(head: bytes) -> str | None:
    for prefix, kind in MAGIC_PREFIXES.items():
        if head.startswith(prefix):
            return kind
    return None


async def coverage_by_chain(session) -> list[tuple[str, int, int, int]]:
    """(chain, total, with_url, malformed) straight from the database."""
    rows = await session.execute(
        text(r"""
            SELECT p.chain,
                   count(*)                                    AS total,
                   count(pp.image_url)                         AS with_url,
                   count(*) FILTER (
                       WHERE pp.image_url IS NOT NULL
                         AND (pp.image_url !~ '^https?://'
                              OR pp.image_url ~ '[[:space:][:cntrl:]]')
                   )                                           AS malformed
            FROM pharmacy_products pp
            JOIN pharmacies p ON p.id = pp.pharmacy_id
            GROUP BY 1
            ORDER BY 2 DESC
        """)
    )
    return [(r[0], r[1], r[2], r[3]) for r in rows]


async def sample_urls(session, per_chain: int, chain: str | None) -> list[tuple[str, str]]:
    rows = await session.execute(
        text("""
            SELECT chain, image_url FROM (
                SELECT p.chain, pp.image_url,
                       row_number() OVER (PARTITION BY p.chain ORDER BY random()) AS rn
                FROM pharmacy_products pp
                JOIN pharmacies p ON p.id = pp.pharmacy_id
                WHERE pp.image_url IS NOT NULL
                  -- asyncpg cannot infer a bare `:chain IS NULL`
                  -- (AmbiguousParameterError), so the cast is required.
                  AND (CAST(:chain AS text) IS NULL OR p.chain = CAST(:chain AS text))
            ) s
            WHERE rn <= :n
        """),
        {"n": per_chain, "chain": chain},
    )
    return [(r[0], r[1]) for r in rows]


async def probe(client: httpx.AsyncClient, url: str) -> tuple[int | str, str | None]:
    """Fetch just enough bytes to identify the format. Returns (status, kind).

    Backs off on 429 rather than counting it: a throttled request tells us
    nothing about whether the image is there, and reporting it as "broken"
    would make the whole check untrustworthy.
    """
    delay = 2.0
    for attempt in range(MAX_429_RETRIES + 1):
        try:
            # Range keeps this cheap: we only need the file header.
            response = await client.get(url, headers={"Range": "bytes=0-15"})
        except Exception as exc:  # noqa: BLE001 — any transport failure is a failure
            return type(exc).__name__, None

        if response.status_code == 429:
            # Out of retries: report as throttled, never as broken. Falling
            # through to the generic `>= 400` branch would file it as a dead
            # image, which is exactly the false alarm this check must not raise.
            if attempt >= MAX_429_RETRIES:
                return "429_throttled", None
            retry_after = response.headers.get("Retry-After")
            wait = float(retry_after) if (retry_after or "").isdigit() else delay
            await asyncio.sleep(min(wait, 30.0))
            delay = min(delay * 2, 30.0)
            continue

        if response.status_code >= 400:
            return response.status_code, None
        return response.status_code, identify(response.content[:16])

    return "429_throttled", None


async def run(per_chain: int, chain: str | None, fail_under: float) -> int:
    async with AsyncSessionLocal() as session:
        rows = await coverage_by_chain(session)
        samples = await sample_urls(session, per_chain, chain)

    print(f"{'chain':<14}{'total':>8}{'con url':>9}{'cobertura':>11}{'malformadas':>13}")
    grand_total = grand_url = grand_bad = 0
    for name, total, with_url, malformed in rows:
        grand_total += total
        grand_url += with_url
        grand_bad += malformed
        print(f"{name:<14}{total:>8}{with_url:>9}{100 * with_url / total:>10.1f}%{malformed:>13}")
    if grand_total:
        print(f"{'TOTAL':<14}{grand_total:>8}{grand_url:>9}"
              f"{100 * grand_url / grand_total:>10.1f}%{grand_bad:>13}")

    if not samples:
        print("\nNo hay URLs para muestrear.")
        return 0

    by_chain: dict[str, list[str]] = collections.defaultdict(list)
    for chain_name, url in samples:
        by_chain[chain_name].append(url)

    # One semaphore per host so a slow/strict CDN cannot be hammered, and a
    # chain on a fast CDN is not held back by one that is not.
    host_locks: dict[str, asyncio.Semaphore] = collections.defaultdict(
        lambda: asyncio.Semaphore(CONCURRENCY_PER_HOST)
    )
    results: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)

    async with httpx.AsyncClient(
        follow_redirects=True, timeout=30,
        limits=httpx.Limits(max_connections=32),
        headers={"User-Agent": ASSET_USER_AGENT},
    ) as client:
        async def one(chain_name: str, url: str) -> None:
            host = httpx.URL(url).host
            async with host_locks[host]:
                status, kind = await probe(client, url)
                await asyncio.sleep(PER_HOST_DELAY_S)
            if status in (200, 206) and kind is not None:
                results[chain_name]["ok"] += 1
            elif status == "429_throttled":
                # Not a verdict on the image — excluded from the health rate.
                results[chain_name]["throttled"] += 1
            else:
                results[chain_name]["bad"] += 1
                results[chain_name][f"  {status}"] += 1

        await asyncio.gather(*(
            one(c, u) for c, urls in by_chain.items() for u in urls
        ))

    print(f"\nAlcanzabilidad (muestra de hasta {per_chain} por cadena):")
    print(f"{'chain':<14}{'probadas':>9}{'ok':>6}{'rotas':>7}{'limit':>7}{'sanas':>9}")
    offenders: list[str] = []
    for name in sorted(results):
        counter = results[name]
        ok, bad, throttled = counter["ok"], counter["bad"], counter["throttled"]
        judged = ok + bad          # throttled requests are not evidence either way
        rate = 100 * ok / judged if judged else 0.0
        shown = f"{rate:>8.1f}%" if judged else f"{'n/d':>9}"
        print(f"{name:<14}{judged + throttled:>9}{ok:>6}{bad:>7}{throttled:>7}{shown}")
        detail = {k.strip(): v for k, v in counter.items() if k.startswith("  ")}
        if detail:
            print(f"{'':<14}fallas: {detail}")
        if throttled:
            print(f"{'':<14}{throttled} con rate-limit tras {MAX_429_RETRIES} reintentos "
                  f"— sin veredicto, baja --sample para esta cadena")
        if judged and rate < fail_under:
            offenders.append(f"{name} {rate:.1f}%")

    if grand_bad:
        print(f"\nAVISO: {grand_bad} URLs malformadas guardadas — "
              f"`normalize_image_url` deberia haberlas filtrado al escribir.")

    if offenders:
        print(f"\nFALLA: por debajo de {fail_under}% alcanzable -> {', '.join(offenders)}")
        return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=int, default=40, help="URLs a probar por cadena")
    parser.add_argument("--chain", default=None, help="Limitar a una cadena")
    parser.add_argument("--fail-under", type=float, default=0.0,
                        help="Exit 1 si alguna cadena baja de este %% alcanzable")
    args = parser.parse_args()
    code = asyncio.run(run(args.sample, args.chain, args.fail_under))
    if code:
        logger.error("check_images fallo")
    raise SystemExit(code)


if __name__ == "__main__":
    main()
