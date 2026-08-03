#!/usr/bin/env python3
"""Mark orphaned `scraping_jobs` rows as failed.

`workers/scraper/src/scheduler.py` inserts a row with `status='running'` before a
scrape starts and updates it to `success`/`failed` when the scrape ends. If the
process dies in between — an interrupted laptop run, a Cloud Run task that hits
`--task-timeout`, an OOM kill — the row stays `running` forever and every
dashboard reading that table shows a phantom in-flight scrape.

Nothing in the scraper cleans those up, so this runs as a separate Cloud Run Job
(`scraper-reaper`) on an hourly Cloud Scheduler trigger. See docs/infra-gcloud.md.

Deliberately standalone: it imports nothing from `workers/scraper/src` and speaks
raw asyncpg, so it keeps working even if the scraper package is refactored. The
only dependency is `asyncpg`, which is already a main dependency of the scraper
image this script ships inside.

Usage:
    python scripts/reap_stale_jobs.py [--older-than-hours N] [--dry-run]

Env:
    DATABASE_URL          required, same URL the scraper uses
    REAP_MAX_AGE_HOURS    default for --older-than-hours (fallback: 3)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from urllib.parse import parse_qsl, unquote, urlsplit

DEFAULT_MAX_AGE_HOURS = 3

# `started_at` is `timestamp without time zone` and scheduler.py fills it with a
# bare NOW(), i.e. the session time zone. Comparing against a bare NOW() here
# uses that same session time zone, so the two agree without hardcoding UTC.
REAP_SQL = """
UPDATE scraping_jobs
   SET status      = 'failed',
       finished_at = NOW(),
       errors      = jsonb_build_object(
           'reaped_by',   'scripts/reap_stale_jobs.py',
           'reason',      'orphaned: still marked running after the max age; '
                          'the process that owned this row never reported back',
           'max_age_hours', $1::int,
           'reaped_at',   to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SSOF'),
           'previous',    errors
       )
 WHERE status = 'running'
   AND started_at < NOW() - make_interval(hours => $1::int)
RETURNING id, pharmacy_chain, started_at
"""

PREVIEW_SQL = """
SELECT id, pharmacy_chain, started_at,
       round(extract(epoch FROM (NOW() - started_at)) / 3600.0, 2) AS age_hours
  FROM scraping_jobs
 WHERE status = 'running'
   AND started_at < NOW() - make_interval(hours => $1::int)
 ORDER BY started_at
"""


def connect_kwargs(url: str) -> dict:
    """Turn a DATABASE_URL into asyncpg.connect kwargs.

    Handles both shapes used in this project:
      postgresql://user:pass@34.176.88.36:5432/farmaciacompare      (laptop, TCP)
      postgresql://user:pass@localhost/farmaciacompare?host=/cloudsql/<conn>
                                                       (Cloud Run, unix socket)

    asyncpg's DSN parser does not reliably honour a `?host=` unix-socket override,
    so the URL is taken apart here instead of handed over whole.
    """
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))

    kwargs: dict = {
        "user": unquote(parts.username) if parts.username else None,
        "password": unquote(parts.password) if parts.password else None,
        "database": (parts.path or "").lstrip("/") or None,
    }

    socket_dir = query.get("host")
    if socket_dir and socket_dir.startswith("/"):
        # Unix socket: asyncpg appends /.s.PGSQL.<port> to the directory.
        kwargs["host"] = socket_dir
    else:
        kwargs["host"] = parts.hostname
        if parts.port:
            kwargs["port"] = parts.port

    return {k: v for k, v in kwargs.items() if v is not None}


async def reap(max_age_hours: int, dry_run: bool) -> int:
    import asyncpg  # imported late so --help works without the dependency

    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set", file=sys.stderr)
        return 2

    conn = await asyncpg.connect(**connect_kwargs(url), timeout=30)
    try:
        rows = await conn.fetch(PREVIEW_SQL, max_age_hours)
        if not rows:
            print(f"reaper: no scraping_jobs stuck in 'running' for more than {max_age_hours}h")
            return 0

        for row in rows:
            print(
                f"reaper: stale {row['pharmacy_chain']:<12} "
                f"started_at={row['started_at']} age={row['age_hours']}h id={row['id']}"
            )

        if dry_run:
            print(f"reaper: --dry-run, {len(rows)} row(s) left untouched")
            return 0

        reaped = await conn.fetch(REAP_SQL, max_age_hours)
        print(f"reaper: marked {len(reaped)} row(s) as failed")
        return 0
    finally:
        await conn.close()


def main() -> int:
    env_default = os.environ.get("REAP_MAX_AGE_HOURS")
    try:
        default_hours = int(env_default) if env_default else DEFAULT_MAX_AGE_HOURS
    except ValueError:
        default_hours = DEFAULT_MAX_AGE_HOURS

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--older-than-hours",
        type=int,
        default=default_hours,
        help=f"age past which a 'running' row counts as orphaned (default: {default_hours})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="list what would be reaped without writing",
    )
    args = parser.parse_args()

    if args.older_than_hours < 0:
        parser.error("--older-than-hours must be >= 0")

    return asyncio.run(reap(args.older_than_hours, args.dry_run))


if __name__ == "__main__":
    raise SystemExit(main())
