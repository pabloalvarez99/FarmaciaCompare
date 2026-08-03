"""CLI smoke tests for cleanup-jobs (no database required)."""

from click.testing import CliRunner

from src.cli import DEFAULT_CLEANUP_HOURS, ORPHAN_ERROR_REASON, main


def test_cleanup_jobs_registered_and_help():
    runner = CliRunner()
    result = runner.invoke(main, ["cleanup-jobs", "--help"])
    assert result.exit_code == 0
    assert "--hours" in result.output
    assert "--dry-run" in result.output
    assert "orphan" in result.output.lower() or "running" in result.output.lower()


def test_cleanup_jobs_rejects_negative_hours():
    runner = CliRunner()
    result = runner.invoke(main, ["cleanup-jobs", "--hours", "-1"])
    assert result.exit_code != 0


def test_orphan_reason_constant():
    assert ORPHAN_ERROR_REASON == "orphaned: exceeded max runtime"
    assert DEFAULT_CLEANUP_HOURS == 2


def test_scheduler_reaps_only_jobs_older_than_a_full_crawl():
    """The startup reaper must not kill a healthy long crawl.

    Cruz Verde's sitemap pass runs ~2h45m. A window any tighter than that would
    mark a working scrape as failed and hand its slot to a second one, which is
    exactly the concurrency the db-f1-micro cannot take.
    """
    import re
    from pathlib import Path

    source = Path(__file__).resolve().parents[1] / "src" / "scheduler.py"
    text = source.read_text(encoding="utf-8")

    match = re.search(
        r"UPDATE scraping_jobs.*?INTERVAL '(\d+) hours'", text, re.S
    )
    assert match, "the startup reaper is gone; ghost rows will accumulate again"
    assert int(match.group(1)) >= 3, "window too tight for a full Cruz Verde crawl"


def test_scheduler_reaper_only_touches_running_rows():
    """A finished job must never be rewritten by the reaper."""
    from pathlib import Path

    source = Path(__file__).resolve().parents[1] / "src" / "scheduler.py"
    reaper = source.read_text(encoding="utf-8").split("UPDATE scraping_jobs", 1)[1]
    reaper = reaper.split("RETURNING", 1)[0]

    assert "status = 'running'" in reaper
