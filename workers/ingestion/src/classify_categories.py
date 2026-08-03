"""Assign a canonical category to every scraped listing.

Until now everything that was not a medicine was noise to be filtered out. With
the scope of `docs/PLAN.md` it is catalog: the 8.880 Preunic listings, the 4.604
of Curie, the deodorants of Farmex are already scraped, with photo and
attributes, and the only thing missing is saying what they are.

Every chain already tells us, each in its own dialect, and it is all sitting in
`pharmacy_products.attributes`. This module maps each chain's dialect onto the
seven categories of `docs/PLAN.md` §2 and writes
`pharmacy_products.category_id`.

    python -m src.classify_categories --dry-run             # count, write nothing
    python -m src.classify_categories --dry-run --sample 15
    python -m src.classify_categories                       # write

Design rules, each of them paid for once already:

  - **Test the negative before the positive.** MercadoFarma publishes
    `medicamento` / `sin medicamento`, and the negative contains the positive.
    A naive substring match mislabelled 2.162 of its 4.970 listings.
  - **A listing that cannot be placed with confidence gets no category**, never
    an invented one. Null is an honest gap; a wrong category makes every facet
    downstream lie. This is why there is no "it is linked to the drug catalog,
    therefore it is a drug" tier — see `_NO_CATALOG_TIER` below.
  - **The chain's own boolean beats the chain's merchandising slug** — but only
    where the boolean is first-party. Cruz Verde's `c_isMedProduct`
    (`ocapi_connector.py`) and MercadoFarma's `product_type`
    (`mercadofarma_connector.py`) are published by the store. Everyone else's
    `isMedicine` is something *our* connector derived from the very breadcrumb
    being read here, so using it as a veto would be circular: it would have
    thrown away Salcobrand's antihypertensives, which live under "Cuidado de la
    Salud" and never say the word "medicamento".
  - **The ladder order is the mapping.** The first rule that matches wins, so
    where two labels overlap the fix is the order, not a longer regex. Every
    ordering constraint below is annotated with the listings that forced it.
  - **Write only what changes**, `executemany` in batches, because the database
    is a db-f1-micro shared with the scrapers.

`_NO_CATALOG_TIER`: an earlier draft gave `medicamento` to any listing already
linked to `medications`, on the theory that the canonical table holds only the
ISP registry and the tu-farmacia drug catalog. Measured against production it
placed 12.768 listings, and a hand-read sample of the Farmex rows it decided
(Talco Simond's, Suerox, Spirulina, Sensodyne toothpaste, Tigel shampoo, Perio
Aid mouthwash, a digital thermometer, an omega-3) was wrong more often than
right. The canonical table is not drugs-only, and 12.707 of those listings carry
no category label at all — the tier was inventing evidence, not reading it. It
was removed; those listings are now honestly NULL.
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass

from loguru import logger

from .db import AsyncSessionLocal  # type: ignore[attr-defined]

BATCH = 500

# --------------------------------------------------------------------------
# The seven categories of docs/PLAN.md §2.
# --------------------------------------------------------------------------
MEDICAMENTO = "medicamento"
SUPLEMENTO = "suplemento"
DERMOCOSMETICA = "dermocosmetica"
COSMETICA = "cosmetica"
HIGIENE = "higiene"
BEBE = "bebe"
DISPOSITIVO = "dispositivo"

# Seeded already in production; `id` is what `pharmacy_products.category_id`
# references. Name and identity_key are only used to create a row that is
# missing — an existing row is never overwritten, see `check_categories`.
CATEGORIES: list[tuple[str, str, str, int]] = [
    (MEDICAMENTO, "Medicamentos",
     "principio activo + concentracion + forma + unidades", 1),
    (SUPLEMENTO, "Suplementos y vitaminas",
     "marca + ingrediente + dosis por porcion + unidades", 2),
    (DERMOCOSMETICA, "Dermocosmetica",
     "marca + linea + variante + volumen", 3),
    (COSMETICA, "Cosmetica y maquillaje",
     "marca + linea + tono + volumen", 4),
    (HIGIENE, "Higiene y cuidado personal",
     "marca + linea + formato + cantidad", 5),
    (BEBE, "Cuidado del bebe",
     "marca + etapa + formato + peso", 6),
    (DISPOSITIVO, "Dispositivos y accesorios",
     "marca + modelo", 7),
]
ORDER = [slug for slug, _n, _k, _p in CATEGORIES]

# Sentinel for a label we recognise and deliberately do not carry: perfumery is
# out of scope by decision (CLAUDE.md §2), and so are pet products, food and
# drink, toys and the houseware/stationery aisles Preunic and Cruz Verde also
# sell. Distinguishing it from "no rule matched" matters: one is a decision, the
# other is a hole in the mapping.
OUT_OF_SCOPE = "__out_of_scope__"

# Chains whose medicine flag is published by the store itself rather than
# derived by our connector from the same text this module reads.
FIRST_PARTY_MEDICINE_FLAG = {"cruz_verde", "mercadofarma"}


# --------------------------------------------------------------------------
# Text folding
# --------------------------------------------------------------------------
def fold(text: str | None) -> str:
    """Accent-free, punctuation-free, space-padded lowercase.

    Padding with spaces lets every rule below use plain `\\b` boundaries and
    never match inside a longer word — the failure mode that turned
    "sin medicamento" into a medicine. Note that Cruz Verde slugs are
    hyphen-separated, so folding is also what turns
    "capilar-mascarillas-tratamientos" into words a rule can see.
    """
    stripped = unicodedata.normalize("NFKD", text or "")
    stripped = stripped.encode("ascii", "ignore").decode("ascii")
    stripped = re.sub(r"[^A-Za-z0-9]+", " ", stripped).strip().lower()
    return f" {stripped} " if stripped else ""


# --------------------------------------------------------------------------
# The ladder. First rule that matches wins, so the order *is* the mapping.
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Rule:
    name: str
    pattern: re.Pattern[str]
    category: str | None  # a slug, or OUT_OF_SCOPE
    broad: bool = False   # a catch-all parent aisle, reported as weak evidence


def _rule(name: str, category: str | None, *alternatives: str, broad: bool = False) -> Rule:
    return Rule(name, re.compile("|".join(alternatives)), category, broad)


LADDER: list[Rule] = [
    # -- out of scope, first, so nothing below can claim them -------------
    _rule("veterinaria", OUT_OF_SCOPE,
          r"\bveterinari", r"\bmascotas?\b", r"\bsalcopets\b", r"\bpet\b",
          r"\bperros?\b", r"\bgatos?\b"),

    # Farmex ships a single "PERFUMERIA Y DERMOCOSMETICA" department. The
    # dermo half is in scope, so it has to be read before the perfume veto.
    _rule("dermo-en-depto-perfumeria", DERMOCOSMETICA,
          r"\bperfumeria y dermocosmetica\b"),
    _rule("perfumeria", OUT_OF_SCOPE,
          r"\bperfum", r"\bfragancias?\b", r"\bcolonias?\b",
          r"\beau de\b", r"\bsplash\b"),

    # Toys before the baby aisle: Salcobrand files 25 listings under
    # "infantil y mama > accesorios > juguetes", and a Lego set is not baby
    # care in any of the seven senses.
    _rule("juguetes", OUT_OF_SCOPE, r"\bjuguetes\b", r"\bjugueteria\b"),

    # -- baby, before hygiene (nappies, wipes) and before houseware
    #    (feeding bottles live next to the kitchenware aisle in Preunic) ---
    #    `paniales` is not a typo: that is the spelling Cruz Verde uses in its
    #    category slugs, and folding does not turn it back into `panales`.
    _rule("bebe", BEBE,
          r"\binfantil y mama\b", r"\binfantil y maternidad\b",
          r"\bmi bebe\b", r"\bbebe y mama\b", r"\bmaternidad\b",
          r"\blactancia\b", r"\bmamaderas?\b", r"\bchupetes?\b",
          r"\bmordedores\b", r"\bformulas? infantil", r"\bformulas lacteas\b",
          r"\bcereales y colados\b", r"\bcoceduras\b",
          r"\bhigiene infantil\b", r"\bpanales para bebe",
          r"\bpanales y wipes\b", r"\bpaniales y wipes\b", r"\bpaniales?\b",
          r"\btoallitas humedas\b", r"\bcuidado infantil\b", r"\bbubu\b",
          r"\bavent\b", r"^ infantil\b",
          # Bare `panales` used to sit in the hygiene rule, next to
          # incontinence. Chains that spell it Cruz Verde's way (`paniales`)
          # landed in bebe while Farmex's `panales` landed in hygiene — the same
          # Babysec pack in two categories depending on the store, which defeats
          # the point of a comparison site. Nappies are overwhelmingly for
          # babies; adult ones announce themselves and keep their own patterns
          # (`panales de adultos`, `incontinencia`) in the hygiene rule.
          r"\bpanales?\b(?!\s*(?:de\s+|para\s+)?adultos?\b)"),

    # -- houseware / stationery: Preunic and Cruz Verde sell them ---------
    _rule("no-salud", OUT_OF_SCOPE,
          r"\bmenaje\b", r"\blibreria\b", r"\bcuadernos?\b",
          r"\bhogar\b", r"\bcontenedores de alimentos\b", r"\btermos?\b",
          r"\bcomplementos de mesa\b", r"\bvasos\b",
          r"\baccesorios de temporada\b", r"\bhermeticos\b",
          r"\bmenaje cocina\b", r"\bmenaje comedor\b"),

    # -- devices and medical supplies, before the word "medicamento" ------
    #    Salcobrand files glucose meters under "Medicamentos > Antiobesidad y
    #    Diabetes > Medidores de Glucosa" and Cruz Verde appends "medicamentos"
    #    to the slug of most device aisles; the device reading is the right one.
    #
    #    `mascarilla` is deliberately NOT here on its own: Cruz Verde's
    #    "capilar-mascarillas-tratamientos" is 56 hair masks, and reading them
    #    as surgical masks was the single worst error of the first draft. The
    #    real device labels all carry their own words ("insumos medicos",
    #    "primeros auxilios", "guantes y mascarillas").
    _rule("dispositivo", DISPOSITIVO,
          r"\baccesorios? medicos?\b", r"\binsumos? medicos?\b",
          r"\bdispositivos? medicos?\b", r"\binsumos y dispositivos\b",
          r"\bequipamiento medico\b", r"\bguantes y mascarillas\b",
          # Lens care is an accessory aisle, but Farmex files it under a tag
          # blob that also carries the word "medicamentos" ("cuidado oftalmico
          # limpieza lentes medicamentos oftalmicos"), so lens wipes were coming
          # back as medicine. Naming the precise label lets it win in the first
          # pass, before the blob gets read.
          r"\blimpieza (?:de )?lentes\b", r"\bestuches? de lentes\b",
          # Named in the note above as one of the real device labels, but it was
          # missing from the list, so `Cuidado Personal > Primeros Auxilios >
          # Mascarillas` fell through to the broad "cuidado personal" rule and
          # surgical masks landed in hygiene. First aid is bandages, gauze and
          # masks — devices, not toiletries.
          r"\bprimeros auxilios\b",
          r"\bmonitores de salud\b", r"\bortopedic", r"\bortesis\b",
          r"\btermometros?\b", r"\btiras reactivas\b", r"\btest de \w+",
          r"\bpruebas test\b", r"\bvendas?\b", r"\bgasas?\b",
          r"\bjeringas\b", r"\bagujas\b", r"\bapositos?\b",
          r"\bnebulizador", r"\baerocamaras?\b", r"\btomador de presion\b",
          r"\bmedidores de glucosa\b", r"\bglucosa\b",
          r"\bespecial diabeticos\b", r"\bcabestrillos\b",
          r"\brodilleras?\b", r"\btobilleras?\b", r"\bmunequeras?\b",
          r"\blentes de contacto\b", r"\bkinesiologico\b",
          r"\bparches y suturas\b", r"\bparches y cintas\b",
          r"\bgasa y tela adhesiva\b", r"\bbotiquin\b"),
    # `curacion` is deliberately absent: as a Farmex/Curie tag it sits on
    # petroleum jelly and baking soda as often as on dressings, and the real
    # dressing aisles already say "insumos medicos" or "primeros auxilios".

    # -- the word "medicamento" itself, above every merchandising bucket --
    #    Farmaloop files Ozempic, Wegovy, Mounjaro and phentermine under
    #    "Medicamentos > Control de Peso"; reading the leaf first made 45
    #    prescription drugs into supplements. Ahumada files 59 antifungals
    #    under "Medicamentos > Dermatológicos", which the skincare rule used
    #    to claim. A chain that writes this word means it.
    _rule("medicamento", MEDICAMENTO,
          r"\bmedicamentos?\b", r"\bmedicinas?\b", r"\bfarmacos?\b",
          r"\brecetario magistral\b", r"\bbioequivalentes?\b",
          r"\bcenabast\b"),

    # -- sun care, before supplements ------------------------------------
    #    Salcobrand's "Dermocoaching > Protección Solar > Rostro > Pantallas
    #    Solares y Minerales" is 67 sunscreens, and the supplement rule used to
    #    claim them on the word "minerales".
    _rule("proteccion-solar", DERMOCOSMETICA,
          r"\bproteccion solar\b", r"\bprotectores? solares?\b",
          r"\bpantallas solares\b", r"\bbloqueadores? solares?\b",
          r"\bbloqueador\b", r"\bfotoprotector", r"\bbronceador"),

    # -- food and drink are not one of the seven --------------------------
    #    Above supplements, not below: Cruz Verde's "vitaminas y suplementos >
    #    alimentos y bebidas > bebestibles / snacks" is 99 listings of Monster,
    #    chocolate-covered peanuts and flavoured water. The department they
    #    hang from does not make them supplements.
    _rule("alimentos", OUT_OF_SCOPE,
          r"\bbebidas y alimentos\b", r"\balimentos y bebidas\b",
          r"\bsnacks?\b", r"\bte e infusiones\b", r"\binfusiones\b",
          r"\baguas jugos", r"\bbebestibles\b", r"\bchocolates\b",
          r"\bendulzante", r"\baceites acetos y vinagres\b",
          r"\bproductos alimenticios\b"),

    # -- supplements ------------------------------------------------------
    _rule("suplemento", SUPLEMENTO,
          r"\bvitaminas?\b", r"\bsuplementos?\b", r"\bmultivitamin",
          r"\bprobiotic", r"\bcolagen", r"\bomegas?\b",
          r"\bantioxidantes?\b", r"\bminerales\b", r"\bmagnesio\b",
          r"\bnutricion deportiva\b", r"\bsuplemento deportivo\b",
          r"\brendimiento deportivo\b", r"\bcrecimiento muscular\b",
          r"\bproteinas?\b", r"\bcontrol de peso\b",
          r"\bquemadores de grasa", r"\binhibidor de apetito",
          r"\bpropoleo\b", r"\benergizantes\b", r"\bsuperalimentos\b",
          r"\besencias florales\b", r"\bgummies\b", r"\bcranberr",
          r"\bcomplejo b\b", r"\bdieta y nutricion\b",
          r"\bnutricion y vitaminas\b", r"\bcuidado y nutricion\b",
          r"\bsistema inmune y defensas\b", r"\bsalud digestiva\b",
          r"\bvitalidad y energia\b", r"\bfitness\b"),

    # -- make-up, before facial care: "belleza > maquillaje > rostro" is
    #    make-up, not skincare, and both mention the face ------------------
    _rule("cosmetica-maquillaje", COSMETICA,
          r"\bmaquillajes?\b", r"\bmake up\b", r"\besmaltes?\b",
          r"\bmanicure\b", r"\blabiales\b", r"\bbrillos labiales\b",
          r"\bbalsamos labiales\b", r"\bdelineador", r"\bdelinedor\b",
          r"\bmascaras de pestanas\b", r"\bpestanas\b", r"\bcejas\b",
          r"\bsombras\b", r"\brubor", r"\bbronzer\b", r"\biluminadores\b",
          r"\bcorrectores\b", r"\bbases\b", r"\bprimer\b", r"\bpolvos\b",
          r"\bunas\b", r"\blapiz modelador\b", r"\blapices\b",
          r"\bencrespadores\b", r"\bbrochas\b"),

    # -- hair care, before facial care so "mascarilla capilar" is hair ----
    _rule("cosmetica-capilar", COSMETICA,
          r"\bcapilar", r"\bshampoos?\b", r"\bacondicionador",
          r"\btinturas?\b", r"\bstyling\b", r"\bcabello\b",
          r"\bcrema para peinar\b", r"\bcremas de peinar\b",
          r"\banticaspa\b", r"\bfijadores\b", r"\bcoloracion\b",
          r"\bretocador de raiz\b", r"\bcepillos y peinetas\b",
          r"\balisado\b"),

    # -- facial care and dermo brands -------------------------------------
    _rule("dermocosmetica", DERMOCOSMETICA,
          r"\bdermocosmetica\b", r"\bdermocoaching\b", r"\bdermatologic",
          r"\bskincare\b", r"\bskin care\b", r"\bskin analyzer\b",
          r"\bcosmetica coreana\b", r"\bcuidado del rostro\b",
          r"\bcuidado de la piel\b", r"\bcuidado piel\b",
          r"\btratamiento rostro\b", r"\blimpieza facial\b",
          r"\blimpiadores faciales\b", r"\bserums?\b", r"\bantiedad\b",
          r"\bantiarrugas\b", r"\bcontorno de ojos\b",
          r"\baguas micelares\b", r"\bmanchas y pigmentadas\b",
          r"\bcremas de dia\b", r"\bmascarillas? facial",
          r"\bfacial\b", r"\brostro\b"),

    # -- hygiene: specific labels only. The broad parents ("cuidado
    #    personal", "adulto mayor") sit further down, below the drug
    #    classes, because Salcobrand files real drugs under them. ---------
    _rule("higiene", HIGIENE,
          r"\bhigiene bucal\b", r"\bcuidado bucal\b", r"\bsalud bucal\b",
          r"\bpastas? dental", r"\bcepillos? de dientes\b",
          r"\bcepillos dentales\b", r"\benjuagues? bucal",
          r"\bdesodorantes?\b", r"\bantitranspirante\b",
          r"\bafeitado\b", r"\bafeitar\b", r"\bdepilacion\b",
          r"\bdepilatorias\b", r"\bjabones\b", r"\bgel de ducha\b",
          r"\btoallas higienicas\b", r"\btoallas\b",
          r"\bcuidado menstrual\b", r"\bproteccion femenina\b",
          r"\bproteccion menstrual\b", r"\bprotectores diarios\b",
          r"\bcuidado mujer\b", r"\bcuidado femenino\b",
          r"\bincontinencia\b", r"\bpanales? (?:de |para )?adultos?\b",
          r"\bropa interior desechable\b", r"\bcuidado corporal\b",
          r"\bbodycare\b", r"\bcremas de cuerpo\b", r"\bcremas de manos\b",
          r"\bmanos y pies\b", r"\bmanos pies\b", r"\bcuidado pies\b",
          r"\btalco", r"\besponjas de bano\b", r"\bhora del banio\b",
          r"\bcuidado hombre\b", r"\bcuidado barba\b",
          r"\bhigiene personal\b", r"\baceites corporales\b",
          r"\bexfoliantes\b", r"\bcelulitis y estrias\b"),

    # -- the therapeutic classes chains use instead of the word
    #    "medicamento" (Farmex publishes "Antidepresivo" and never
    #    "Medicamento"). Below the category rules above because a class name
    #    is weaker evidence than a department name. ------------------------
    _rule("clase-terapeutica", MEDICAMENTO,
          r"\banalgesic", r"\banalgesia\b", r"\banestesic",
          r"\banemia\b", r"\bansiolitic", r"\bantiacido",
          r"\bantiacne", r"\bantialergic", r"\bantiartros",
          r"\bantiasmatic", r"\bantibiotic", r"\banticoagulante",
          r"\banticonceptiv", r"\banticonvulsi", r"\bantidepresiv",
          r"\bantidiarreic", r"\bantiemetic", r"\bantiepileptic",
          r"\bantiespasmodic", r"\bantiflatulento", r"\bantifungic",
          r"\bantigotoso", r"\bantigripal", r"\bantihistaminic",
          r"\bantihipertensiv", r"\bantiinfeccios", r"\bantiiinflamator",
          r"\bantiinflamator", r"\bantimicotic", r"\bantiparasitari",
          r"\bantiprurito\b", r"\bantipsicotic", r"\bantirreumatic",
          r"\bantisepticos?\b", r"\bantitrombotic", r"\bantitusiv",
          r"\bantiulceros", r"\bantiviral", r"\balergias?\b",
          r"\balopecia\b", r"\balzheimer\b", r"\barritmia\b", r"\basma\b",
          r"\bbroncodilatador", r"\bcardiovascular\b",
          r"\bcardiometabolico\b", r"\bcicatrizantes\b", r"\bcolesterol\b",
          r"\bcorticoide", r"\bcorticoesteroide", r"\bdiabet",
          r"\bdiuretic", r"\bdisfuncion erectil\b", r"\bdolor y fiebre\b",
          r"\bdolor estomacal\b", r"\bdolor\b", r"\bepilepsia\b",
          r"\bestabilizadores del animo\b", r"\bexpectorante",
          r"\bfiebre\b", r"\bgastric", r"\bglaucoma\b", r"\bhemorroides\b",
          r"\bhipertens", r"\bhipoglicemiante", r"\bhipolipemiante",
          r"\bhipotensor", r"\bhipotiroidismo\b", r"\bhormonas\b",
          r"\binductores? del sueno\b", r"\binmunosupresor",
          r"\binmunoterapia\b", r"\binsulina\b", r"\blaxante",
          r"\bmetabolic", r"\bmigrana\b", r"\bnauseas y vomitos\b",
          r"\bneurolept", r"\boftalmic", r"\boftalmolog", r"\boncologic",
          r"\bosteoporosis\b", r"\bparkinson\b", r"\bprostata\b",
          r"\brelajante muscular\b", r"\bsalud mental\b",
          r"\bsistema nervioso\b", r"\bsistema digestivo\b",
          r"\bsistema respiratorio\b", r"\bsistema cardiovascular\b",
          r"\bsistema circulatorio\b", r"\btiroides\b",
          r"\btranquilizante", r"\btumores malignos\b", r"\bvertigo\b",
          r"\bmedicina reproductiva\b", r"\btratamientos biologicos\b",
          r"\bcoadyuvantes\b"),

    # -- broad parents. Reported separately as weak evidence: these are
    #    catch-all aisles, right far more often than not but never precise.
    _rule("higiene-generico", HIGIENE,
          r"\bhigiene\b", r"\bcuidado personal\b",
          r"\bcuidado adulto mayor\b", r"\badulto mayor\b",
          r"\bcuidado adulto\b", r"\bbienestar sexual\b",
          r"\bsalud sexual\b", r"\bpreservativos?\b",
          r"\blubricantes\b", r"\bvida sexual\b",
          r"\bsalud mujer\b", r"\bsalud hombre\b",
          r"\bcuerpo\b", r"\bcorporal\b", r"\bspa\b", broad=True),

    _rule("belleza-generico", COSMETICA,
          r"\bbelleza\b", r"\bcosmetic", broad=True),
]

BROAD_RULES = {rule.name for rule in LADDER if rule.broad}


def match_ladder(
    text: str, allow_medicine: bool = True, allow_broad: bool = True
) -> tuple[str | None, str] | None:
    """First rule that fires, or None if the text says nothing we understand.

    `allow_broad=False` skips the catch-all parent aisles at the bottom of the
    ladder, so a caller with more than one label to read can ask the precise
    question of every label before settling for the vague one.
    """
    if not text:
        return None
    for rule in LADDER:
        if rule.category == MEDICAMENTO and not allow_medicine:
            continue
        if rule.broad and not allow_broad:
            continue
        if rule.pattern.search(text):
            return rule.category, rule.name
    return None


# --------------------------------------------------------------------------
# What each chain publishes, and in what order to read it
# --------------------------------------------------------------------------
# MercadoFarma's `product_type` is a yes/no medicine flag, not a category. The
# negative must be tested first: "sin medicamento" contains "medicamento", and
# testing the positive first mislabelled 2.162 of its 4.970 listings. The
# misspellings the store actually publishes -- "sin medicaento",
# "sin medicamnto", "sin medicamentos" -- all start with "sin", so anchoring on
# that word catches them without enumerating them.
_MF_NEGATIVE = re.compile(r"^ sin\b")
_MF_POSITIVE = re.compile(r"\bmedicam|\bmedicin|\bfarmac")
_MF_NO_SIGNAL = {"no aplica", "no disponible", "fnl", "n a", "", "-"}


def mercadofarma_medicine(product_type: str | None) -> bool | None:
    """True / False / None when the published value decides nothing."""
    folded = fold(product_type)
    if folded.strip() in _MF_NO_SIGNAL:
        return None
    if _MF_NEGATIVE.search(folded):
        return False
    if _MF_POSITIVE.search(folded):
        return True
    return None


def _as_text_list(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str)]
    return []


def declared_sources(chain: str, attributes: dict) -> list[str]:
    """The chain's own category labels, best evidence first.

    Each element is tried against the ladder in turn, so a weaker field never
    overrides a stronger one. Curie is the reason: 216 of its listings carry
    the tag "dermocosmetica" *and* the product type "Medicamentos"; reading
    both as one blob would file paracetamol under skincare.
    """
    category = attributes.get("category")
    primary = _as_text_list(category)

    if chain == "farmaloop":
        # `productCategory` and `productSubCategory` are two halves of one
        # label: "Cuidado y Belleza" alone cannot tell dental from make-up.
        primary += _as_text_list(attributes.get("subCategory"))
        return [fold(" ".join(primary))]

    if chain == "ahumada":
        return [fold(" ".join(primary + _as_text_list(attributes.get("categoryLeaf"))))]

    sources = [fold(" ".join(primary))] if primary else []

    if chain == "preunic":
        # `category` is the leaf and is often a merchandising bucket
        # ("pack y estuches"); the path carries the aisle it hangs from.
        path = _as_text_list(attributes.get("categoryPath"))
        if path:
            sources.append(fold(" ".join(path)))
    elif chain in ("curie", "knop", "mercadofarma", "farmex"):
        tags = _as_text_list(attributes.get("tags"))
        if tags:
            sources.append(fold(" ".join(tags)))

    return [s for s in sources if s]


def truthy(value) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        low = value.strip().lower()
        if low in ("true", "1", "yes"):
            return True
        if low in ("false", "0", "no"):
            return False
    return None


def classify(chain: str, attributes: dict | None) -> tuple[str | None, str]:
    """Return `(category slug or None, reason)` for one listing.

    Nothing here looks at the product name or at `medication_id`: the only
    evidence is what the chain declared. A listing whose chain declared nothing
    usable comes back `(None, ...)`.
    """
    attributes = attributes if isinstance(attributes, dict) else {}

    is_medicine = truthy(attributes.get("isMedicine"))
    if chain == "mercadofarma":
        is_medicine = mercadofarma_medicine(attributes.get("category"))

    # Cruz Verde's `c_isMedProduct` and MercadoFarma's `product_type` are
    # published by the store. They beat the merchandising slug, which is why
    # they are read before the ladder and not after: Cruz Verde files real
    # drugs under "dermatologia" and non-drugs under promo slugs that say
    # "medicamentos".
    first_party = chain in FIRST_PARTY_MEDICINE_FLAG
    if first_party and is_medicine is True:
        return MEDICAMENTO, "flag-tienda"

    allow_medicine = not (first_party and is_medicine is False)

    # Two passes over the chain's labels. The precise rules get to see every
    # label before the catch-all parents get to see any: Farmex files Colgate
    # toothpaste under the department "COSMETICO" and only its tags say
    # "cuidado bucal", and Curie files a Dove conditioner under "cuidado
    # personal" with "acondicionador" only in the tags. Letting the broad rule
    # on the first label win would answer "beauty" and "hygiene" to questions
    # the second label answers exactly.
    sources = declared_sources(chain, attributes)
    for allow_broad in (False, True):
        for index, text in enumerate(sources):
            hit = match_ladder(
                text, allow_medicine=allow_medicine, allow_broad=allow_broad
            )
            if hit is None:
                continue
            category, rule_name = hit
            suffix = "" if index == 0 else f"+{index}"
            if category is OUT_OF_SCOPE:
                return None, f"fuera-de-alcance:{rule_name}{suffix}"
            return category, f"regla:{rule_name}{suffix}"

    # Derived flag, used only once the declared labels have said nothing.
    # Farmex is why: its `product_type` holds a therapeutic class for drugs and
    # a department for everything else, so the classes the ladder does not know
    # still land here with the connector's flag set.
    if allow_medicine and is_medicine is True:
        return MEDICAMENTO, "flag-derivado"

    return None, "sin-etiqueta" if not sources else "sin-regla"


# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------
# Insert-only. The seven rows already exist in production with names chosen by
# the main thread; re-seeding must not rename them behind its back.
SEED_CATEGORY = """
    INSERT INTO categories (id, name, identity_key, position, created_at)
    VALUES (:id, :name, :identity_key, :position, NOW())
    ON CONFLICT (id) DO NOTHING
"""

UPDATE_LISTING = """
    UPDATE pharmacy_products
    SET category_id = :category_id, updated_at = NOW()
    WHERE id = :id
"""

UPDATE_MEDICATION = """
    UPDATE medications
    SET category_id = :category_id, updated_at = NOW()
    WHERE id = :id
"""

# A canonical row takes the category its listings agree on. Below this share it
# keeps none: a canonical product whose category is a coin flip is worse than
# one with no category at all.
MEDICATION_VOTE_MIN = 0.67


async def _write(session, statement: str, rows: list[dict], label: str) -> None:
    from sqlalchemy import text

    stmt = text(statement)
    written = 0
    for start in range(0, len(rows), BATCH):
        chunk = rows[start : start + BATCH]
        await session.execute(stmt, chunk)
        await session.commit()
        written += len(chunk)
        logger.info(f"  {label}: {written}/{len(rows)}")


async def check_categories(session, dry_run: bool) -> None:
    """Report which of the seven exist; create only the missing ones."""
    from sqlalchemy import text

    present = {
        row[0]
        for row in (await session.execute(text("SELECT id FROM categories"))).fetchall()
    }
    missing = [c for c in CATEGORIES if c[0] not in present]
    if not missing:
        logger.info(f"categorías presentes: {len(ORDER)}/7, nada que sembrar")
        return
    logger.info(f"categorías faltantes: {[c[0] for c in missing]}")
    if dry_run:
        logger.info("dry-run: no se sembró ninguna")
        return
    await session.execute(
        text(SEED_CATEGORY),
        [
            {"id": slug, "name": name, "identity_key": key, "position": position}
            for slug, name, key, position in missing
        ],
    )
    await session.commit()


async def classify_all(
    dry_run: bool = False, sample: int = 0, with_canonical: bool = False
) -> dict:
    from sqlalchemy import text

    async with AsyncSessionLocal() as session:
        await check_categories(session, dry_run)

        rows = (
            await session.execute(
                text(
                    """
                    SELECT pp.id, ph.chain, pp.attributes, pp.medication_id,
                           pp.category_id, pp.raw_name
                    FROM pharmacy_products pp
                    JOIN pharmacies ph ON ph.id = pp.pharmacy_id
                    ORDER BY pp.id
                    """
                )
            )
        ).fetchall()
        logger.info(f"listados leídos: {len(rows)}")

        by_category: Counter[str] = Counter()
        by_chain: dict[str, Counter[str]] = defaultdict(Counter)
        by_reason: Counter[str] = Counter()
        rules_per_category: dict[str, Counter[str]] = defaultdict(Counter)
        unresolved: dict[str, Counter[str]] = defaultdict(Counter)
        samples: dict[str, dict[str, list[tuple[str, str]]]] = defaultdict(
            lambda: defaultdict(list)
        )
        votes: dict[str, Counter[str]] = defaultdict(Counter)

        listing_updates: list[dict] = []
        for listing_id, chain, attributes, medication_id, current, raw_name in rows:
            category, reason = classify(chain, attributes)
            key = category or "SIN CATEGORIA"
            by_category[key] += 1
            by_chain[chain][key] += 1
            by_reason[reason] += 1
            rules_per_category[key][reason] += 1
            if category is None:
                unresolved[chain][reason] += 1
            if sample:
                samples[key][chain].append((raw_name or "", reason))
            if medication_id and category:
                votes[str(medication_id)][category] += 1
            if category != current:
                listing_updates.append({"id": str(listing_id), "category_id": category})

        logger.info(f"listados que cambian: {len(listing_updates)} de {len(rows)}")

        medication_updates: list[dict] = []
        undecided = 0
        if with_canonical:
            current_medication = {
                str(mid): cat
                for mid, cat in (
                    await session.execute(
                        text("SELECT id, category_id FROM medications")
                    )
                ).fetchall()
            }
            for medication_id, tally in votes.items():
                total = sum(tally.values())
                winner, count = tally.most_common(1)[0]
                if count / total < MEDICATION_VOTE_MIN:
                    undecided += 1
                    continue
                if current_medication.get(medication_id) != winner:
                    medication_updates.append(
                        {"id": medication_id, "category_id": winner}
                    )
            logger.info(
                f"canónicos con voto: {len(votes)}, sin mayoría "
                f"{MEDICATION_VOTE_MIN:.0%}: {undecided}, que cambian: "
                f"{len(medication_updates)}"
            )

        report(
            by_category, by_chain, by_reason, rules_per_category,
            unresolved, samples, len(rows), sample,
        )

        if dry_run:
            logger.info("dry-run: no se escribió nada")
        else:
            if listing_updates:
                await _write(
                    session, UPDATE_LISTING, listing_updates, "pharmacy_products"
                )
            if medication_updates:
                await _write(
                    session, UPDATE_MEDICATION, medication_updates, "medications"
                )

    return {
        "listings": len(rows),
        "listings_changed": len(listing_updates),
        "medications_changed": len(medication_updates),
        "sin_categoria": by_category.get("SIN CATEGORIA", 0),
    }


def stratified(per_chain: dict[str, list[tuple[str, str]]], n: int) -> list[tuple[str, str, str]]:
    """Round-robin over chains so a sample of N is not all one store."""
    chains = sorted(per_chain, key=lambda c: -len(per_chain[c]))
    picked: list[tuple[str, str, str]] = []
    depth = 0
    while len(picked) < n and any(len(per_chain[c]) > depth for c in chains):
        for chain in chains:
            if len(picked) >= n:
                break
            if len(per_chain[chain]) > depth:
                name, reason = per_chain[chain][depth]
                picked.append((chain, name, reason))
        depth += 1
    return picked


def report(
    by_category, by_chain, by_reason, rules_per_category,
    unresolved, samples, total, sample,
) -> None:
    order = ORDER + ["SIN CATEGORIA"]

    print("\n== por categoría ==")
    for slug in order:
        count = by_category.get(slug, 0)
        print(f"  {slug:<16} {count:>7}  {count / total:>6.1%}")
    print(f"  {'TOTAL':<16} {total:>7}")

    print("\n== por cadena ==")
    print("  " + f"{'cadena':<14}" + "".join(f"{s[:12]:>13}" for s in order) + f"{'total':>10}")
    for chain in sorted(by_chain):
        line = f"  {chain:<14}"
        for slug in order:
            line += f"{by_chain[chain].get(slug, 0):>13}"
        print(line + f"{sum(by_chain[chain].values()):>10}")

    print("\n== por regla ==")
    for reason, count in by_reason.most_common():
        print(f"  {reason:<34} {count:>7}")

    print("\n== evidencia débil: categorías apoyadas en un cajón genérico ==")
    for slug in ORDER:
        rules = rules_per_category.get(slug)
        if not rules:
            continue
        total_slug = sum(rules.values())
        weak = sum(
            n for r, n in rules.items()
            if any(r.startswith(f"regla:{b}") for b in BROAD_RULES)
            or r == "flag-derivado"
        )
        secondary = sum(n for r, n in rules.items() if r.endswith(("+1", "+2")))
        flag = "  <-- REVISAR" if total_slug and weak / total_slug > 0.20 else ""
        print(
            f"  {slug:<16} {total_slug:>7}   genérica {weak:>6} "
            f"({weak / total_slug:>5.1%})   por campo 2º {secondary:>6}{flag}"
        )

    print("\n== sin clasificar, por cadena y motivo ==")
    for chain in sorted(unresolved):
        for reason, count in unresolved[chain].most_common():
            print(f"  {chain:<14} {reason:<28} {count:>7}")

    if sample:
        print(f"\n== muestra de {sample} por categoría (repartida entre cadenas) ==")
        for slug in order:
            per_chain = samples.get(slug)
            if not per_chain:
                continue
            print(f"\n-- {slug} --")
            for chain, name, reason in stratified(per_chain, sample):
                print(f"  [{chain:<12}] {name[:70]:<70} {reason}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Classify scraped listings into the seven canonical categories"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count and report without writing a single row",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=0,
        help="Print N example listings per category for eyeballing",
    )
    parser.add_argument(
        "--with-canonical",
        action="store_true",
        help=(
            "Also give medications.category_id the category its listings vote "
            "for. Off by default: the task at hand is pharmacy_products, and "
            "this touches a second table."
        ),
    )
    args = parser.parse_args()
    logger.info(
        "Listo: "
        + str(
            asyncio.run(
                classify_all(
                    dry_run=args.dry_run,
                    sample=args.sample,
                    with_canonical=args.with_canonical,
                )
            )
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
