import os
from pathlib import Path

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

    def test_dosage_from_product_title(self):
        row = {
            "NUMERO_REGISTRO": "F-18790/16",
            "NOMBRE_PRODUCTO": "PLENICA 75 CÁPSULAS 75 mg",
            "PRINCIPIO_ACTIVO": "PREGABALINA",
            "LABORATORIO": "DEUTSCHE PHARMA S.A.",
        }
        record = ISPRecord.from_row(row)
        assert record.dosage == "75mg"
        assert record.pharmaceutical_form == "capsula"


class TestISPImporter:
    SAMPLE_CSV = os.path.join(os.path.dirname(__file__), "..", "data", "isp_sample.csv")
    OFFICIAL_DIR = Path(__file__).resolve().parent.parent / "data" / "official"

    def test_load_sample_csv(self):
        importer = ISPImporter()
        records = importer.load_csv(self.SAMPLE_CSV)
        assert len(records) >= 5
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

    def test_load_venta_directa_style(self, tmp_path):
        csv_file = tmp_path / "venta.csv"
        csv_file.write_text(
            "N° Registro;Nombre Producto;Razon Social Titular;Condicion Venta\n"
            "B-1000/10;PARACETAMOL 500 MG COMPRIMIDOS;LABORATORIO CHILE S.A.;Directa\n",
            encoding="latin-1",
        )
        importer = ISPImporter()
        records = importer.load_csv(str(csv_file), source="venta_directa")
        assert len(records) == 1
        assert records[0].isp_registration == "B-1000/10"
        assert records[0].dosage == "500mg"
        assert records[0].prescription_required is False

    def test_load_bioequiv_style(self, tmp_path):
        csv_file = tmp_path / "bioequiv.csv"
        csv_file.write_text(
            ";;Listado de productos Bioequivalentes;;;;;\n"
            "N°;Principio Activo;Producto ;Registro;Titular;Estado;Vigencia;Uso / Tratamiento\n"
            "1;PREGABALINA;PLENICA 75 CÁPSULAS 75 mg ;F-18790/16;DEUTSCHE PHARMA S.A.;EQUIVALENTE TERAPÉUTICO;Sí;Anticonvulsivantes\n",
            encoding="latin-1",
        )
        importer = ISPImporter()
        records = importer.load_csv(str(csv_file), source="bioequiv")
        assert len(records) == 1
        assert records[0].isp_registration == "F-18790/16"
        assert records[0].active_ingredient == "Pregabalina"
        assert records[0].dosage == "75mg"
