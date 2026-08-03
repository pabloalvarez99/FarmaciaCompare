from src.places_discovery import (
    REGIONS,
    infer_chain,
    looks_like_pharmacy,
    place_region_matches,
    region_from_components,
)


def _aa1(long_name):
    return [{"types": ["administrative_area_level_1", "political"], "long_name": long_name}]


def test_region_from_components_known():
    # Strings Google actually returns for administrative_area_level_1.
    assert region_from_components(_aa1("Coquimbo")) == "Coquimbo"
    assert region_from_components(_aa1("Región Metropolitana")) == "Metropolitana"
    assert region_from_components(_aa1("Región Metropolitana de Santiago")) == "Metropolitana"
    assert region_from_components(_aa1("Valparaíso")) == "Valparaíso"
    assert region_from_components(_aa1("Región del Biobío")) == "Biobío"
    assert region_from_components(_aa1("Región del Maule")) == "Maule"
    assert region_from_components(_aa1("Región de La Araucanía")) == "Araucanía"


def test_region_from_components_unknown_is_none():
    # None → caller falls back to the queried region rather than dropping.
    assert region_from_components(None) is None
    assert region_from_components([]) is None
    assert region_from_components(_aa1("Antofagasta")) is None
    assert region_from_components([{"types": ["locality"], "long_name": "Coquimbo"}]) is None


def _cl(long_name):
    return _aa1(long_name) + [{"types": ["country", "political"], "short_name": "CL"}]


def test_place_region_matches_same_region():
    assert place_region_matches(_cl("Región Metropolitana"), "Metropolitana") is True
    assert place_region_matches(_cl("Coquimbo"), "Coquimbo") is True


def test_place_region_matches_rejects_other_chilean_region():
    # Real leak: "farmacia Providencia Santiago" returned a La Serena pharmacy.
    assert place_region_matches(_cl("Coquimbo"), "Metropolitana") is False


def test_place_region_matches_rejects_unmapped_chilean_region():
    # Ñuble is not in our alias table; it is still not Metropolitana.
    assert place_region_matches(_cl("Ñuble"), "Metropolitana") is False


def test_place_region_matches_rejects_foreign_country():
    # region=cl is only a bias: results landed in República Dominicana.
    foreign = _aa1("Santiago") + [{"types": ["country"], "short_name": "DO"}]
    assert place_region_matches(foreign, "Metropolitana") is False


def test_place_region_matches_allows_missing_components():
    # --no-details runs carry no components; do not drop everything.
    assert place_region_matches(None, "Metropolitana") is True
    assert place_region_matches([], "Metropolitana") is True
    assert place_region_matches([{"types": ["country"], "short_name": "CL"}], "Maule") is True


def test_region_specs_emit_canonical_names():
    # Every region we can discover must resolve back to its own canonical name,
    # otherwise strict_region would drop every result it finds.
    for spec in REGIONS.values():
        assert region_from_components(_aa1(spec.name)) == spec.name


def test_infer_chain_known():
    assert infer_chain("Farmacias Cruz Verde") == "cruz_verde"
    assert infer_chain("Salcobrand La Serena") == "salcobrand"
    assert infer_chain("Farmacias Ahumada ex Magnae") == "ahumada"
    assert infer_chain("Farmacia Dr. Simi") == "dr_simi"
    assert infer_chain("Knop La Serena") == "knop"
    assert infer_chain("Farmacia Dr. Amigo - 24 Horas") == "dr_amigo"


def test_infer_chain_independent():
    assert infer_chain("Farmacia Don Pedro") is None


def test_looks_like_pharmacy_type_pharmacy():
    assert looks_like_pharmacy("Random Store", ["pharmacy", "point_of_interest"]) is True
    assert looks_like_pharmacy("", ["pharmacy"]) is True


def test_looks_like_pharmacy_name_generic():
    assert looks_like_pharmacy("Farmacia Don Pedro", ["store"]) is True
    assert looks_like_pharmacy("Botica del Centro", []) is True


def test_looks_like_pharmacy_name_chains():
    assert looks_like_pharmacy("Cruz Verde La Serena", ["store"]) is True
    assert looks_like_pharmacy("Salcobrand Mall Plaza", []) is True
    assert looks_like_pharmacy("Farmacias Ahumada", []) is True
    assert looks_like_pharmacy("Dr. Simi Coquimbo", []) is True
    assert looks_like_pharmacy("Farmacias Similares", []) is True
    assert looks_like_pharmacy("Knop Ovalle", []) is True
    assert looks_like_pharmacy("Dr Amigo 24H", []) is True
    assert looks_like_pharmacy("Tempofarma", []) is True


def test_looks_like_pharmacy_rejects_noise():
    # Real noise from Places text search "farmacia {city}"
    assert looks_like_pharmacy(
        "Comercializadora De Articulos Ortopedicos",
        ["store", "point_of_interest"],
    ) is False
    assert looks_like_pharmacy("Óptica Visión Clara", ["store"]) is False
    assert looks_like_pharmacy("Optica del Sol", []) is False
    assert looks_like_pharmacy("Laboratorio Clínico Norte", ["health"]) is False
    assert looks_like_pharmacy("Clínica Veterinaria Amigos", []) is False
    assert looks_like_pharmacy("Perfumería París", ["store"]) is False


def test_looks_like_pharmacy_allows_farmacia_plus_vertical():
    # Name has farmacia → keep even if other vertical words appear
    assert looks_like_pharmacy("Farmacia Veterinaria del Sur", []) is True
    assert looks_like_pharmacy("Farmacia y Óptica Central", []) is True


def test_looks_like_pharmacy_rejects_unrelated():
    assert looks_like_pharmacy("Supermercado Lider", ["supermarket"]) is False
    assert looks_like_pharmacy("Comercializadora XYZ", ["store"]) is False
    assert looks_like_pharmacy("", []) is False

def test_looks_like_pharmacy_farma_prefix():
    from src.places_discovery import looks_like_pharmacy
    assert looks_like_pharmacy('EasyFarma')
    assert looks_like_pharmacy('FarmaVid')
    assert looks_like_pharmacy('Sociedad Farmaceutica Salamanca Ltda.')
    assert looks_like_pharmacy('Favibar Almacen Farmaceutico')
    assert not looks_like_pharmacy('Comercializadora De Articulos Ortopedicos')
    assert not looks_like_pharmacy('EXOPLANET Urgencias Veterinaria 24 Horas')
