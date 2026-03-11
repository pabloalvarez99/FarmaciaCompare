import pytest
import os
from src.isp_importer import ISPImporter, ISPRecord


class TestISPRecord:
    def test_parse_from_row(self):
        row = {
            "NUMERO_REGISTRO": "F-20001",
            "NOMBRE_PRODUCTO": "TAPSIN FORTE COMPRIMIDOS",
            "PRINCIPIO_ACTIVO": "PARACETAMOL",
            "FORMA_FARMACEUTICA": "COMPRIMIDO",
            "CONCENTRACION": "500 MG",
            "LABORATORIO": "LAB CHILE S.A.",
            "VIA_ADMINISTRACION": "ORAL",
            "REQUIERE_RECETA": "NO",
        }
        record = ISPRecord.from_row(row)
        assert record.isp_registration == "F-20001"
        assert record.product_name == "TAPSIN FORTE COMPRIMIDOS"
        assert record.active_ingredient == "Paracetamol"
        assert record.pharmaceutical_form == "comprimido"
        assert record.dosage == "500mg"
        assert record.laboratory == "LAB CHILE S.A."
        assert record.prescription_required is False

    def test_prescription_required_si(self):
        row = {
            "NUMERO_REGISTRO": "F-20003",
            "NOMBRE_PRODUCTO": "AMOXICILINA 500MG",
            "PRINCIPIO_ACTIVO": "AMOXICILINA",
            "FORMA_FARMACEUTICA": "CAPSULA",
            "CONCENTRACION": "500 MG",
            "LABORATORIO": "LAB BETA",
            "VIA_ADMINISTRACION": "ORAL",
            "REQUIERE_RECETA": "SI",
        }
        record = ISPRecord.from_row(row)
        assert record.prescription_required is True


class TestISPImporter:
    SAMPLE_CSV = os.path.join(os.path.dirname(__file__), "..", "data", "isp_sample.csv")

    def test_load_csv(self):
        importer = ISPImporter()
        records = importer.load_csv(self.SAMPLE_CSV)
        assert len(records) == 5
        names = [r.active_ingredient for r in records]
        assert "Paracetamol" in names

    def test_load_csv_temp(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "NUMERO_REGISTRO,NOMBRE_PRODUCTO,PRINCIPIO_ACTIVO,FORMA_FARMACEUTICA,"
            "CONCENTRACION,LABORATORIO,VIA_ADMINISTRACION,REQUIERE_RECETA\n"
            "F-20001,TAPSIN FORTE,PARACETAMOL,COMPRIMIDO,500 MG,LAB CHILE,ORAL,NO\n"
        )
        importer = ISPImporter()
        records = importer.load_csv(str(csv_file))
        assert len(records) == 1
        assert records[0].active_ingredient == "Paracetamol"
