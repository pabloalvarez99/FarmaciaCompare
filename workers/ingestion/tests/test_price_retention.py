"""Tests for the `prices` retention policy.

The planners are pure functions on purpose, so the rules can be pinned down
without a database. What the suite is really guarding is two things:

  - **the invariant** — a plan never contains the latest accepted row of a
    product, because deleting it makes the product vanish from the site in
    silence instead of raising;
  - **dry-run really is dry** — the default path must not emit a DELETE, and
    that is asserted against a fake session rather than trusted.

`--apply` is never run against production, so the write path is covered here
with the same fake session.
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta

import pytest

from src.price_retention import (
    DEFAULT_COMPACT_AFTER_DAYS,
    DEFAULT_QUARANTINE_DAYS,
    PriceRow,
    _assert_invariant,
    plan_full_prune,
    plan_intraday_compaction,
    run_retention,
    summarize,
)

DAY = date(2026, 7, 1)
OTHER_DAY = date(2026, 7, 2)
BASE = datetime(2026, 7, 1, 9, 0)


def row(rid: str, price: int, minute: int, product: str = "p1", day: date = DAY) -> PriceRow:
    """A `prices` row `minute` minutes into the day."""
    return PriceRow(
        id=rid,
        pharmacy_product_id=product,
        day=day,
        price=price,
        recorded_at=BASE + timedelta(minutes=minute),
    )


def ids(rows: list[PriceRow]) -> set[str]:
    return {r.id for r in rows}


def five_row_day() -> list[PriceRow]:
    """One product, one day, five rows — min, max and close are three distinct
    rows, so compaction drops exactly `a` and `d`."""
    return [
        row("a", 1000, 0),
        row("b", 500, 10),   # min
        row("c", 2000, 20),  # max
        row("d", 1500, 30),
        row("e", 1200, 40),  # close
    ]


# ------------------------------------------------------------------ Regla 2


class TestIntradayCompaction:
    def test_keeps_min_max_and_close(self):
        """Five rows in a day collapse to the cheapest, the dearest and the last."""
        rows = [
            row("a", 1000, 0),
            row("b", 500, 10),   # min
            row("c", 2000, 20),  # max
            row("d", 1500, 30),
            row("e", 1200, 40),  # close
        ]
        assert ids(plan_intraday_compaction(rows)) == {"a", "d"}

    def test_three_rows_are_left_alone_when_all_three_are_distinguished(self):
        """Three rows survive only when min, max and close are three *different*
        rows — here the close is neither the cheapest nor the dearest."""
        rows = [row("a", 500, 0), row("b", 2000, 10), row("c", 1200, 20)]
        assert plan_intraday_compaction(rows) == []

    def test_three_rows_lose_the_opening_when_the_close_is_also_the_max(self):
        """min, max and close can collide, and then fewer than three rows remain.

        Ascending prices are the common case: the opening row is neither the
        cheapest nor the dearest nor the last, so it goes. This is the documented
        trade-off — the day's opening is the one thing compaction gives up — not
        an off-by-one.
        """
        rows = [row("a", 1000, 0), row("b", 500, 10), row("c", 2000, 20)]
        assert ids(plan_intraday_compaction(rows)) == {"a"}

    def test_two_rows_are_always_left_alone(self):
        rows = [row("a", 1000, 0), row("b", 500, 10)]
        assert plan_intraday_compaction(rows) == []

    def test_single_row_is_left_alone(self):
        assert plan_intraday_compaction([row("a", 1000, 0)]) == []

    def test_empty_input(self):
        assert plan_intraday_compaction([]) == []

    def test_flat_price_keeps_first_and_last(self):
        """A day where only stock moved keeps the two rows holding the transition.

        Every price is equal, so min and max both resolve to the earliest row and
        the plan keeps the first and the last — which is where a stock change is
        visible. This is the tie-break the docstring promises.
        """
        rows = [row(c, 1000, i * 10) for i, c in enumerate("abcd")]
        assert ids(plan_intraday_compaction(rows)) == {"b", "c"}

    def test_duplicate_max_keeps_the_earlier_one(self):
        """On a price tie the *earliest* row wins, for the max as well as the min.

        Regression guard for the tie-break: it used to be expressed by negating
        `recorded_at` through `datetime.timestamp()`, which reinterprets a naive
        UTC value in the machine's local zone and inverts this ordering for rows
        recorded near a DST transition.
        """
        rows = [
            row("a", 100, 0),   # min
            row("b", 900, 10),  # max, first occurrence — kept
            row("c", 300, 20),
            row("d", 900, 30),  # max, later duplicate — dropped
            row("e", 200, 40),  # close
        ]
        assert ids(plan_intraday_compaction(rows)) == {"c", "d"}

    def test_duplicate_min_keeps_the_earlier_one(self):
        rows = [
            row("a", 100, 0),   # min, first occurrence — kept
            row("b", 900, 10),  # max
            row("c", 100, 20),  # min, later duplicate — dropped
            row("d", 300, 30),
            row("e", 200, 40),  # close
        ]
        assert ids(plan_intraday_compaction(rows)) == {"c", "d"}

    def test_full_tie_breaks_on_lowest_id(self):
        """Same price and same instant: the lowest id is the one kept."""
        same = datetime(2026, 7, 1, 9, 0)
        rows = [
            PriceRow("zzz", "p1", DAY, 500, same),
            PriceRow("aaa", "p1", DAY, 500, same),
            PriceRow("mmm", "p1", DAY, 900, same + timedelta(minutes=5)),
            PriceRow("nnn", "p1", DAY, 700, same + timedelta(minutes=9)),
        ]
        plan = ids(plan_intraday_compaction(rows))
        assert "aaa" not in plan  # lowest id wins the min tie
        assert "zzz" in plan

    def test_input_order_does_not_change_the_plan(self):
        """The plan must not depend on how the database happened to sort rows."""
        rows = [
            row("a", 1000, 0),
            row("b", 500, 10),
            row("c", 2000, 20),
            row("d", 1500, 30),
            row("e", 1200, 40),
        ]
        expected = ids(plan_intraday_compaction(rows))
        rnd = random.Random(20260802)
        for _ in range(25):
            shuffled = rows[:]
            rnd.shuffle(shuffled)
            assert ids(plan_intraday_compaction(shuffled)) == expected

    def test_products_are_independent(self):
        """Two products sharing a day are compacted separately."""
        rows = [
            row("a1", 1000, 0, product="p1"),
            row("a2", 500, 10, product="p1"),
            row("a3", 2000, 20, product="p1"),
            row("a4", 1200, 30, product="p1"),
            row("b1", 1000, 0, product="p2"),
            row("b2", 500, 10, product="p2"),
        ]
        assert ids(plan_intraday_compaction(rows)) == {"a1"}

    def test_days_are_independent(self):
        """The same product on two days is compacted per day, not across days."""
        rows = [
            row("a1", 1000, 0, day=DAY),
            row("a2", 500, 10, day=DAY),
            row("a3", 2000, 20, day=DAY),
            row("a4", 1200, 30, day=DAY),
            row("b1", 1000, 0, day=OTHER_DAY),
            row("b2", 500, 10, day=OTHER_DAY),
        ]
        assert ids(plan_intraday_compaction(rows)) == {"a1"}

    def test_protected_row_is_never_planned(self):
        """A protected id is withheld even when the rule would delete it."""
        rows = [
            row("a", 1000, 0),
            row("b", 500, 10),
            row("c", 2000, 20),
            row("d", 1500, 30),
            row("e", 1200, 40),
        ]
        assert ids(plan_intraday_compaction(rows)) == {"a", "d"}
        assert ids(plan_intraday_compaction(rows, frozenset({"a"}))) == {"d"}
        assert plan_intraday_compaction(rows, frozenset({"a", "d"})) == []

    def test_compaction_preserves_min_max_and_close(self):
        """Whatever the data, the survivors keep the day's low, high and close.

        This is the property the whole rule exists to guarantee: the chart drawn
        from the compacted table has the same daily candle as the raw one.
        """
        rnd = random.Random(1337)
        for _ in range(300):
            n = rnd.randint(1, 12)
            rows = [row(f"r{i}", rnd.randint(100, 9999), i * 7) for i in range(n)]
            doomed = ids(plan_intraday_compaction(rows))
            kept = [r for r in rows if r.id not in doomed]

            assert kept, "a day can never be emptied"
            assert min(r.price for r in kept) == min(r.price for r in rows)
            assert max(r.price for r in kept) == max(r.price for r in rows)
            assert max(kept, key=lambda r: r.recorded_at).id == rows[-1].id
            assert len(kept) <= 3

    def test_keeps_at_most_three_rows_per_day(self):
        """A day never keeps more than min, max and close — and never fewer.

        The kept count is the size of that *set*, so it drops below three
        whenever two of the three land on the same row. With monotonically
        rising prices the max and the close are always the same row, which is
        why a long ascending day compacts down to two.
        """
        for n in range(1, 9):
            rows = [row(f"r{i}", 1000 + i, i * 5) for i in range(n)]
            kept = n - len(plan_intraday_compaction(rows))
            assert kept == min(n, 2)  # ascending: max and close coincide

        for n in range(3, 9):
            # A dip in the middle keeps min, max and close distinct.
            prices = [2000] + [500] * (n - 2) + [1200]
            rows = [row(f"r{i}", prices[i], i * 5) for i in range(n)]
            kept = n - len(plan_intraday_compaction(rows))
            assert kept == 3


# ------------------------------------------------- Regla 1 y Regla 3


class TestFullPrune:
    def test_returns_everything_unprotected(self):
        rows = [row("a", 100, 0), row("b", 200, 10)]
        assert ids(plan_full_prune(rows)) == {"a", "b"}

    def test_withholds_protected_rows(self):
        rows = [row("a", 100, 0), row("b", 200, 10)]
        assert ids(plan_full_prune(rows, frozenset({"b"}))) == {"a"}

    def test_all_protected_yields_empty_plan(self):
        rows = [row("a", 100, 0), row("b", 200, 10)]
        assert plan_full_prune(rows, frozenset({"a", "b"})) == []

    def test_empty_input(self):
        assert plan_full_prune([]) == []


class TestInvariantGuard:
    def test_passes_on_a_clean_plan(self):
        _assert_invariant([row("a", 100, 0)], frozenset({"b"}), "test")

    def test_raises_when_a_live_price_is_in_the_plan(self):
        with pytest.raises(RuntimeError, match="protegidas"):
            _assert_invariant([row("a", 100, 0)], frozenset({"a"}), "test")

    def test_empty_plan_is_fine(self):
        _assert_invariant([], frozenset({"a"}), "test")


class TestSummarize:
    def test_empty(self):
        assert summarize([]) == {
            "rows": 0, "products": 0, "first": None, "last": None, "days": {}
        }

    def test_counts_rows_products_and_days(self):
        rows = [
            row("a", 100, 0, product="p1", day=DAY),
            row("b", 200, 30, product="p2", day=DAY),
            row("c", 300, 60, product="p1", day=OTHER_DAY),
        ]
        s = summarize(rows)
        assert s["rows"] == 3
        assert s["products"] == 2
        assert s["first"] == BASE
        assert s["last"] == BASE + timedelta(minutes=60)
        assert s["days"] == {DAY: 2, OTHER_DAY: 1}


# ------------------------------------------------------------ run_retention

# A fake session standing in for the database, so the write path can be
# exercised without one. It dispatches on the SQL text because that is what
# `run_retention` actually hands it.


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class FakeSession:
    def __init__(self, *, stale_quarantine=(), compaction=(), over_age=(),
                 latest_accepted=(), latest_quarantine=(), total_rows=1000):
        self.stale_quarantine = list(stale_quarantine)
        self.compaction = list(compaction)
        self.over_age = list(over_age)
        self.latest_accepted = list(latest_accepted)
        self.latest_quarantine = list(latest_quarantine)
        self.total_rows = total_rows
        self.deleted_ids: list[str] = []
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def commit(self):
        self.commits += 1

    @staticmethod
    def _as_tuples(rows):
        return [(r.id, r.pharmacy_product_id, r.day, r.price, r.recorded_at) for r in rows]

    async def execute(self, stmt, params=None):
        sql = str(stmt)
        if "DELETE FROM prices" in sql:
            self.deleted_ids.extend(p["id"] for p in params)
            return FakeResult([])
        if "pg_total_relation_size" in sql:
            return FakeResult([(
                self.total_rows, 394 * self.total_rows,
                datetime(2026, 7, 1), datetime(2026, 8, 2),
            )])
        if "DISTINCT ON" in sql:
            source = self.latest_quarantine if "source = 'quarantine'" in sql \
                else self.latest_accepted
            return FakeResult([(i,) for i in source])
        if "busy" in sql:
            return FakeResult(self._as_tuples(self.compaction))
        if "source = 'quarantine'" in sql:
            return FakeResult(self._as_tuples(self.stale_quarantine))
        return FakeResult(self._as_tuples(self.over_age))


@pytest.fixture
def patch_session(monkeypatch):
    def _install(session):
        monkeypatch.setattr(
            "src.price_retention._session_factory", lambda: (lambda: session)
        )
        return session
    return _install


class TestRunRetention:
    @pytest.mark.asyncio
    async def test_dry_run_plans_but_never_deletes(self, patch_session):
        """The default path reports a plan and emits no DELETE at all."""
        session = patch_session(FakeSession(
            stale_quarantine=[row("q1", 100, 0), row("q2", 100, 10)],
            compaction=five_row_day(),
            latest_accepted=["e"],
            latest_quarantine=["q2"],
        ))
        stats = await run_retention(apply=False)

        assert stats["quarantine_planned"] == 1          # q2 is the latest, held back
        assert stats["compaction_planned"] == 2          # a, d
        assert stats["planned_total"] == 3
        assert stats["deleted"] == 0
        assert session.deleted_ids == []
        assert session.commits == 0

    @pytest.mark.asyncio
    async def test_apply_deletes_exactly_the_plan(self, patch_session):
        session = patch_session(FakeSession(
            stale_quarantine=[row("q1", 100, 0), row("q2", 100, 10)],
            compaction=five_row_day(),
            latest_accepted=["e"],
            latest_quarantine=["q2"],
        ))
        stats = await run_retention(apply=True)

        assert stats["deleted"] == 3
        assert set(session.deleted_ids) == {"q1", "a", "d"}
        assert session.commits == 1

    @pytest.mark.asyncio
    async def test_latest_accepted_row_is_never_deleted(self, patch_session):
        """Even if a rule reaches the live price, it does not go in the plan."""
        session = patch_session(FakeSession(
            compaction=[row(c, 1000, i * 10) for i, c in enumerate("abcd")],
            latest_accepted=["a", "b", "c", "d"],
        ))
        stats = await run_retention(apply=True)

        assert stats["planned_total"] == 0
        assert session.deleted_ids == []

    @pytest.mark.asyncio
    async def test_rule_three_is_off_unless_asked(self, patch_session):
        over_age = [row("old1", 100, 0), row("old2", 200, 10)]
        session = patch_session(FakeSession(over_age=over_age))

        off = await run_retention(apply=False)
        assert off["max_age_planned"] == 0

        session = patch_session(FakeSession(over_age=over_age))
        on = await run_retention(apply=False, max_age_days=90)
        assert on["max_age_planned"] == 2

    @pytest.mark.asyncio
    async def test_a_row_reached_by_two_rules_is_deleted_once(self, patch_session):
        """Rules 2 and 3 overlap; the row must appear once in the plan."""
        shared = [row(c, 1000 + i * 100, i * 10) for i, c in enumerate("abcde")]
        session = patch_session(FakeSession(
            compaction=shared, over_age=shared, latest_accepted=["e"],
        ))
        stats = await run_retention(apply=True, max_age_days=90)

        assert len(session.deleted_ids) == len(set(session.deleted_ids))
        assert set(session.deleted_ids) == {"a", "b", "c", "d"}
        assert stats["planned_total"] == 4

    @pytest.mark.asyncio
    async def test_max_deletes_caps_the_plan_oldest_first(self, patch_session):
        session = patch_session(FakeSession(
            stale_quarantine=[row(f"q{i}", 100, i * 10) for i in range(6)],
            latest_quarantine=["q5"],
        ))
        stats = await run_retention(apply=True, max_deletes=2)

        assert stats["planned_total"] == 5
        assert stats["deleted"] == 2
        assert session.deleted_ids == ["q0", "q1"]

    @pytest.mark.asyncio
    async def test_nothing_to_do_is_not_an_error(self, patch_session):
        session = patch_session(FakeSession())
        stats = await run_retention(apply=True)
        assert stats["planned_total"] == 0
        assert session.deleted_ids == []


# -------------------------------------------------------------------- CLI


class TestCli:
    def test_dry_run_and_apply_are_mutually_exclusive(self, monkeypatch):
        from src import price_retention

        monkeypatch.setattr(
            "sys.argv", ["price_retention", "--dry-run", "--apply"]
        )
        with pytest.raises(SystemExit):
            price_retention.main()

    @pytest.mark.parametrize("flag", ["--quarantine-days", "--compact-after-days",
                                      "--max-age-days"])
    def test_rejects_non_positive_thresholds(self, monkeypatch, flag):
        from src import price_retention

        monkeypatch.setattr("sys.argv", ["price_retention", flag, "0"])
        with pytest.raises(SystemExit):
            price_retention.main()

    def test_defaults_are_conservative(self):
        """Quarantine is pruned later than the intraday detail is compacted."""
        assert DEFAULT_QUARANTINE_DAYS == 30
        assert DEFAULT_COMPACT_AFTER_DAYS == 7
        assert DEFAULT_QUARANTINE_DAYS > DEFAULT_COMPACT_AFTER_DAYS
