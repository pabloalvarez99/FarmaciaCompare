import pytest
from unittest.mock import AsyncMock, MagicMock
from src.db_writer import DatabaseWriter
from src.isp_importer import ISPRecord


@pytest.fixture
def sample_record():
    return ISPRecord(
        isp_registration="F-20001",
        product_name="TAPSIN FORTE",
        active_ingredient="Paracetamol",
        active_ingredient_normalized="paracetamol",
        pharmaceutical_form="comprimido",
        dosage="500mg",
        laboratory="Laboratorio Chile",
        route_of_administration="oral",
        prescription_required=False,
    )


class TestDatabaseWriter:
    @pytest.mark.asyncio
    async def test_upsert_creates_records(self, sample_record):
        """Writer should call session.add for new ingredient and medication."""
        mock_session = AsyncMock()
        # Simulate no existing medication (returns None)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        writer = DatabaseWriter(mock_session)
        result = await writer.upsert_record(sample_record)

        assert result == "created"
        assert mock_session.add.called

    @pytest.mark.asyncio
    async def test_skips_existing_registration(self, sample_record):
        """Should skip when ISP registration already exists."""
        mock_existing = MagicMock()
        mock_existing.isp_registration = "F-20001"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_existing
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        writer = DatabaseWriter(mock_session)
        result = await writer.upsert_record(sample_record)
        assert result == "skipped"
