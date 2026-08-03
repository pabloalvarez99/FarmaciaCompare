"""Unit tests for PriceWriter — image_url persistence, isMedicine pass-through, price gates.

No real DB: session + matcher are mocked.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call

import pytest

from src.base_scraper import ScrapedProduct
from src.matcher import MatchResult
from src.price_writer import PriceWriter


PHARMACY_ID = "pharm-test-001"
PP_ID = "pp-uuid-001"


def _product(**overrides) -> ScrapedProduct:
    base = dict(
        sku="SKU-1",
        name="Paracetamol 500 mg 20 comprimidos",
        brand="Genfar",
        laboratory=None,
        price=1990,
        original_price=None,
        discount_pct=None,
        stock_status="in_stock",
        stock_quantity=None,
        barcode=None,
        url="https://example.com/p/1",
        image_url="https://cdn.example.com/img/1.jpg",
        pharmacy_chain="test",
        source="scraper",
        attributes={"isMedicine": True},
    )
    base.update(overrides)
    return ScrapedProduct(**base)


def _row_result(row):
    """Mock for session.execute(...).fetchone() → row."""
    result = MagicMock()
    result.fetchone.return_value = row
    return result


def _writer(session=None, matcher=None) -> PriceWriter:
    session = session or AsyncMock()
    matcher = matcher or MagicMock()
    return PriceWriter(session=session, pharmacy_id=PHARMACY_ID, matcher=matcher)


class TestImageUrlPersistence:
    @pytest.mark.asyncio
    async def test_insert_params_include_image_url(self):
        session = AsyncMock()
        # write_product INSERT returns unlinked row; price path needs last-price SELECT.
        session.execute = AsyncMock(
            side_effect=[
                _row_result((PP_ID, None)),  # INSERT pharmacy_products
                _row_result(None),  # SELECT last price
                MagicMock(),  # INSERT prices
            ]
        )
        matcher = MagicMock()
        matcher.match.return_value = None
        matcher.should_auto_link.return_value = False

        product = _product(image_url="https://cdn.example.com/photo.webp")
        writer = _writer(session=session, matcher=matcher)
        out = await writer.write_product(product)

        assert out["pharmacy_product_id"] == PP_ID
        insert_params = session.execute.call_args_list[0].args[1]
        assert insert_params["image_url"] == "https://cdn.example.com/photo.webp"
        assert insert_params["sku"] == "SKU-1"
        assert insert_params["pharmacy_id"] == PHARMACY_ID

    @pytest.mark.asyncio
    async def test_empty_image_url_becomes_none(self):
        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[
                _row_result((PP_ID, None)),
                _row_result(None),
                MagicMock(),
            ]
        )
        matcher = MagicMock()
        matcher.match.return_value = None
        matcher.should_auto_link.return_value = False

        product = _product(image_url="")
        await _writer(session=session, matcher=matcher).write_product(product)

        insert_params = session.execute.call_args_list[0].args[1]
        assert insert_params["image_url"] is None


class TestIsMedicinePassThrough:
    @pytest.mark.asyncio
    async def test_is_medicine_false_passed_to_matcher(self):
        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[
                _row_result((PP_ID, None)),  # unlinked product
                _row_result(None),
                MagicMock(),
            ]
        )
        matcher = MagicMock()
        matcher.match.return_value = None
        matcher.should_auto_link.return_value = False

        product = _product(
            name="Shampoo Argan 400 mL",
            attributes={"isMedicine": False, "category": "cuidado"},
        )
        writer = _writer(session=session, matcher=matcher)
        out = await writer.write_product(product)

        matcher.match.assert_called_once()
        kwargs = matcher.match.call_args.kwargs
        assert kwargs.get("is_medicine") is False
        assert out["medication_id"] is None
        assert writer.stats["unlinked"] == 1
        matcher.should_auto_link.assert_called()

    @pytest.mark.asyncio
    async def test_is_medicine_snake_case_alias(self):
        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[
                _row_result((PP_ID, None)),
                _row_result(None),
                MagicMock(),
            ]
        )
        matcher = MagicMock()
        matcher.match.return_value = None
        matcher.should_auto_link.return_value = False

        product = _product(attributes={"is_medicine": False})
        await _writer(session=session, matcher=matcher).write_product(product)

        assert matcher.match.call_args.kwargs.get("is_medicine") is False

    @pytest.mark.asyncio
    async def test_is_medicine_true_can_auto_link(self):
        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[
                _row_result((PP_ID, None)),
                MagicMock(),  # UPDATE medication_id
                _row_result(None),  # last price
                MagicMock(),  # INSERT price
            ]
        )
        matcher = MagicMock()
        match = MatchResult(
            medication_id="med-99",
            matched_name="paracetamol 500 mg 20 comprimidos",
            confidence=0.95,
            method="fuzzy",
            grey_zone=False,
        )
        matcher.match.return_value = match
        matcher.should_auto_link.return_value = True

        product = _product(attributes={"isMedicine": True})
        out = await _writer(session=session, matcher=matcher).write_product(product)

        assert matcher.match.call_args.kwargs.get("is_medicine") is True
        assert out["medication_id"] == "med-99"


class TestPriceGates:
    @pytest.mark.asyncio
    async def test_zero_price_skipped(self):
        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[_row_result((PP_ID, "already-linked"))]
        )
        matcher = MagicMock()

        product = _product(price=0)
        out = await _writer(session=session, matcher=matcher).write_product(product)

        assert out["price_action"] == "skipped_zero"
        # Only the pharmacy_products upsert — no price SELECT/INSERT.
        assert session.execute.await_count == 1
        matcher.match.assert_not_called()

    @pytest.mark.asyncio
    async def test_negative_price_skipped(self):
        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[_row_result((PP_ID, "already-linked"))]
        )
        out = await _writer(session=session).write_product(_product(price=-10))
        assert out["price_action"] == "skipped_zero"

    @pytest.mark.asyncio
    async def test_below_floor_quarantined(self):
        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[
                _row_result((PP_ID, "med-1")),  # already linked
                _row_result(None),  # no last price
                MagicMock(),  # quarantine INSERT
            ]
        )
        writer = _writer(session=session)
        # 50 CLP < MIN_PLAUSIBLE_CLP (200)
        out = await writer.write_product(_product(price=50))

        assert out["price_action"] == "quarantined"
        assert writer.stats["quarantined"] == 1

        # Last execute should be the prices INSERT with source quarantine.
        last_sql = str(session.execute.call_args_list[-1].args[0])
        last_params = session.execute.call_args_list[-1].args[1]
        assert "quarantine" in last_sql or last_params.get("price") == 50
        # Params for quarantine path hard-code source in SQL, price in binds:
        assert last_params["price"] == 50
        assert last_params["ppid"] == PP_ID

    @pytest.mark.asyncio
    async def test_catastrophic_drop_quarantined(self):
        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[
                _row_result((PP_ID, "med-1")),
                _row_result((12990, None, "in_stock")),  # last accepted
                MagicMock(),
            ]
        )
        writer = _writer(session=session)
        # 1500 < 15% of 12990 → drop rule
        out = await writer.write_product(_product(price=1500))

        assert out["price_action"] == "quarantined"
        assert writer.stats["quarantined"] == 1

    @pytest.mark.asyncio
    async def test_normal_price_inserted(self):
        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[
                _row_result((PP_ID, "med-1")),
                _row_result(None),
                MagicMock(),
            ]
        )
        writer = _writer(session=session)
        out = await writer.write_product(_product(price=1990))

        assert out["price_action"] == "inserted"
        assert writer.stats["price_rows"] == 1
        last_params = session.execute.call_args_list[-1].args[1]
        assert last_params["price"] == 1990
        assert last_params["source"] == "scraper"

    @pytest.mark.asyncio
    async def test_single_unit_below_general_floor_inserted(self):
        """The writer must hand the name to check_price.

        Without it the single-unit floor can never fire, and this row — a real
        Farmaloop listing at 90 CLP — goes to quarantine on every single run.
        """
        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[
                _row_result((PP_ID, "med-1")),
                _row_result(None),  # no last price
                MagicMock(),
            ]
        )
        writer = _writer(session=session)
        out = await writer.write_product(
            _product(price=90, name="Aguja Hipodérmica 27 g x 1/2 x 1 Unidad")
        )

        assert out["price_action"] == "inserted"
        assert writer.stats["quarantined"] == 0
        last_params = session.execute.call_args_list[-1].args[1]
        assert last_params["price"] == 90
        assert last_params["source"] == "scraper"

    @pytest.mark.asyncio
    async def test_cheap_medicine_still_quarantined(self):
        """Same price, name with no single-unit phrase → unchanged behaviour."""
        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[
                _row_result((PP_ID, "med-1")),
                _row_result(None),
                MagicMock(),
            ]
        )
        writer = _writer(session=session)
        out = await writer.write_product(
            _product(price=90, name="Amlodipino 10 mg x 30 comprimidos.")
        )

        assert out["price_action"] == "quarantined"
        assert writer.stats["quarantined"] == 1


