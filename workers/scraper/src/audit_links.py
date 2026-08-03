"""Audit the product↔catalog links already written to production.

Two kinds of link exist in `pharmacy_products.medication_id`:

  - **Backed by an exact EAN** — the scraped barcode is in `medications.barcodes`.
    That is identity, not heuristic, so it needs no auditing.
  - **Written by the fuzzy matcher** — everything else. Those are the ones that
    can be wrong, and a wrong link shows a user the price of a different
    medicine. This module measures how many are wrong, and why.

It is **read-only**. It never writes a link, never removes one. Its output is a
number we did not have: the link error rate.

    python -m src.audit_links                 # full audit, summary
    python -m src.audit_links --limit 2000    # sample
    python -m src.audit_links --show 40       # print suspect examples
"""
from __future__ import annotations

import argparse
import asyncio
import re
from collections import Counter
from dataclasses import dataclass, field

from loguru import logger

from .product_identity import ProductIdentity, extract_form, is_medical_dosage

# Two ingredient words joined by a slash: "Sacubitrilo / Valsartán". Letters on
# both sides, so a dose ratio ("50/12,5") or a unit ("mg/mL") is not mistaken
# for a combination.
COMBINATION_RE = re.compile(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{4,}\s*/\s*[A-Za-zÁÉÍÓÚÑáéíóúñ]{4,}")

# Routes and presentations that describe HOW a product is given, never WHICH one
# it is. A disagreement here means a different product even when the molecule
# and the strength match — an oral suspension is not a vaginal pessary.
ROUTE_TOKENS = {
    "oftalmica", "oftalmico", "otica", "otico", "nasal", "ocular", "oral",
    "vaginal", "topica", "topico", "rectal", "inhalacion", "sublingual",
}


# Categories where two different brands are two different products. Medicine is
# absent on purpose: a generic and its brand-name equivalent are the same drug,
# and treating the brand as identity there would undo bioequivalence matching.
_BRAND_IS_IDENTITY = frozenset(
    {"cosmetica", "higiene", "dermocosmetica", "bebe", "dispositivo"}
)

# `suplemento` is deliberately absent, measured rather than assumed. A generic
# supplement is named after its ingredient — `Magnesio 400 mg x 60 comprimidos`,
# `Spirulina 500 mg x 90 cápsulas` — and the brand is only whoever bottled it.
# Two magnesium 400 mg jars of 60 from different distributors ARE the comparable
# product, exactly as a generic paracetamol and Panadol are. Including the
# category cost 14 correct links out of 17 flagged; the 3 real errors it caught
# were dermocosmetics and devices, which stay covered above.
#
# Branded supplements (Centrum, Ensure) are not thereby unprotected: they still
# have to survive the dose, pack-size and form gates like everything else.


def _normalise(value: str | None) -> str:
    """Accent-folded lowercase, so `Katmandú` matches `KATMANDU`."""
    return ProductIdentity.from_name(value or "").normalized


def _content_words(value: str | None) -> set[str]:
    """Letter-only words of length > 2 — the ones that carry identity.

    Split on non-alphanumerics rather than whitespace: the catalogue writes
    `OPTI-FREE`, and treating that as a single token made it share nothing with
    a listing that writes `Opti Free`. Anything containing a digit is dropped
    because it is a size (`100ml`, `355`), and two products of the same size are
    not thereby the same product — counting it as shared evidence let a Bulldog
    moisturiser pass as a Lacoste one.
    """
    return {
        word
        for word in re.findall(r"[a-z]+", _normalise(value))
        if len(word) > 2
    }


@dataclass
class Finding:
    category: str
    product_name: str
    catalog_name: str
    detail: str


@dataclass
class AuditReport:
    checked: int = 0
    ean_backed: int = 0
    suspect: int = 0
    by_category: Counter = field(default_factory=Counter)
    examples: list[Finding] = field(default_factory=list)

    @property
    def error_rate(self) -> float:
        return (self.suspect / self.checked * 100) if self.checked else 0.0


def _route_of(text: str) -> str | None:
    """The route named in a title, if any."""
    for token in ProductIdentity.from_name(text or "").normalized.split():
        if token in ROUTE_TOKENS:
            return token
    return None


def _is_combination(text: str | None) -> bool:
    return bool(text) and bool(COMBINATION_RE.search(text))


def classify(
    product_name: str,
    catalog_name: str,
    ambiguous: set[str],
    brand: str | None = None,
    category_id: str | None = None,
) -> Finding | None:
    """Return a Finding when this link looks wrong, else None.

    Every rule here corresponds to a false positive that was observed in
    production, not to a hypothetical.
    """
    query = ProductIdentity.from_name(product_name or "")
    candidate = ProductIdentity.from_name(catalog_name or "")

    # Outside medicine, the brand IS the identity, and ignoring it let four
    # different shampoos — Eucerin Dermocapillaire, Le Petit Olivier, Katmandú —
    # collapse onto `ALL OUT SHAMPOO 250 ML PEDIC`, a head-lice treatment. The
    # site published that as a $3.999 saving between a dandruff shampoo and a
    # pediculicide.
    #
    # The rule is deliberately narrow. For a medicine, brand is *not* identity:
    # a generic paracetamol and Panadol are the same product, which is the whole
    # point of the bioequivalence catalogue. So this only runs for categories
    # where a different brand means a different product.
    if category_id in _BRAND_IS_IDENTITY and brand:
        catalog_words = _content_words(catalog_name)
        brand_words = [w for w in re.findall(r"[a-z]+", _normalise(brand)) if len(w) > 2]
        if brand_words and not any(w in catalog_words for w in brand_words):
            # A missing brand is not proof on its own. `brand` sometimes holds
            # the manufacturer rather than the product line — ALCON for
            # Opti-Free — and the catalogue abbreviates — `H.TROP.GEL ICE AFTER
            # SUN` for Hawaiian Tropic. Both are correct links that the literal
            # brand test rejected, so the titles get a say: when they still
            # share two distinctive words, the pair is left alone.
            shared = _content_words(product_name) & catalog_words
            # Measured on a 10-listing sample of what this rule cuts, roughly
            # one in ten is a correct link lost — `BIODERMA Sensibio Ar Crema`
            # against `SENSIBIO-AR 40 ML` is the same product, with the house
            # brand dropped from the catalogue name. Exempting a single shared
            # long word was tried and rejected: `original` and `vitamina` are
            # eight characters and carry no identity at all, so the exemption
            # spared more wrong links than right ones. Telling a product line
            # from a generic noun needs a vocabulary, not a length.
            #
            # The rule ships with that error rate because the costs are not
            # symmetric: a lost link costs one comparison, a kept one shows a
            # shopper the price of a different product.
            if len(shared) < 2:
                return Finding(
                    "marca_distinta", product_name, catalog_name,
                    f"{brand} no aparece en el catálogo",
                )

    # `Blissel Estriol 5 mg` linked to `estriol 0.5 mg`: a 10x strength error.
    q_med, c_med = is_medical_dosage(query.dosage), is_medical_dosage(candidate.dosage)
    # A ratio and an absolute are not comparable: `Betametasona 4 mg/mL` in a 1 mL
    # ampoule *is* `BETAMETASONA 4 MG`. Flagging that pair as a strength mismatch
    # cut correct links for every injectable and oral solution whose catalog row
    # states the dose per unit instead of per mL. Unequal only counts when both
    # sides speak the same way.
    q_ratio, c_ratio = "/" in (query.dosage or ""), "/" in (candidate.dosage or "")
    if q_ratio != c_ratio:
        q_med = c_med = False
    if q_med and c_med and query.dosage != candidate.dosage:
        return Finding(
            "dosis_distinta", product_name, catalog_name,
            f"{query.dosage} vs {candidate.dosage}",
        )

    # `Levetiracetam 300 mL` linked to `KOPODEX 120ML`: less product, same price
    # shown as a saving.
    if query.pack_volume_ml and candidate.pack_volume_ml and query.pack_volume_ml != candidate.pack_volume_ml:
        return Finding(
            "volumen_distinto", product_name, catalog_name,
            f"{query.pack_volume_ml} mL vs {candidate.pack_volume_ml} mL",
        )

    # `Indometacina 30 cápsulas` linked to `INDOMETACINA 24COM.`
    if query.pack_count and candidate.pack_count and query.pack_count != candidate.pack_count:
        return Finding(
            "envase_distinto", product_name, catalog_name,
            f"{query.pack_count} vs {candidate.pack_count} unidades",
        )

    # Nystatin oral suspension linked to the vaginal pessary.
    q_route, c_route = _route_of(product_name), _route_of(catalog_name)
    if q_route and c_route and q_route != c_route:
        return Finding("via_distinta", product_name, catalog_name, f"{q_route} vs {c_route}")

    q_form, c_form = extract_form(query.normalized), extract_form(candidate.normalized)
    if q_form and c_form and q_form != c_form:
        return Finding("forma_distinta", product_name, catalog_name, f"{q_form} vs {c_form}")

    # `Concor AM` (bisoprolol + amlodipine) priced as plain bisoprolol.
    if _is_combination(product_name) and not _is_combination(catalog_name):
        return Finding("combo_a_componente", product_name, catalog_name, "combo → un componente")

    # `insulina 100 ui ml` names Actrapid, Apidra, Insulatard, Humalog and
    # Tresiba at once. Picking one is a lottery among pharmacologically
    # different drugs.
    if candidate.normalized in ambiguous:
        return Finding("clave_ambigua", product_name, catalog_name, "el catálogo comparte esa clave")

    return None


async def audit(limit: int = 0, show: int = 0) -> AuditReport:
    from sqlalchemy import text

    from .db import AsyncSessionLocal

    report = AuditReport()

    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                text("""
                    SELECT normalized_name
                    FROM medication_names
                    GROUP BY normalized_name
                    HAVING COUNT(DISTINCT medication_id) > 1
                """)
            )
        ).fetchall()
        ambiguous = {r[0] for r in rows}
        logger.info(f"claves ambiguas en el catálogo: {len(ambiguous)}")

        query = """
            SELECT pp.raw_name,
                   m.name,
                   (pp.barcode IS NOT NULL AND pp.barcode <> '' AND pp.barcode = ANY(m.barcodes)) AS ean_backed,
                   pp.brand,
                   pp.category_id
            FROM pharmacy_products pp
            JOIN medications m ON m.id = pp.medication_id
            WHERE pp.is_active = true
        """
        if limit:
            query += f" LIMIT {int(limit)}"

        for product_name, catalog_name, ean_backed, brand, category_id in (
            await session.execute(text(query))
        ).fetchall():
            report.checked += 1
            if ean_backed:
                # Exact barcode identity. Nothing to second-guess.
                report.ean_backed += 1
                continue
            finding = classify(product_name, catalog_name, ambiguous, brand, category_id)
            if finding:
                report.suspect += 1
                report.by_category[finding.category] += 1
                if len(report.examples) < max(show, 40):
                    report.examples.append(finding)

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0, help="Sample size (0 = all)")
    parser.add_argument("--show", type=int, default=0, help="Print N suspect examples")
    args = parser.parse_args()

    report = asyncio.run(audit(args.limit, args.show))
    fuzzy = report.checked - report.ean_backed

    print(f"\nvínculos revisados        {report.checked}")
    print(f"  respaldados por EAN     {report.ean_backed}  (identidad exacta)")
    print(f"  escritos por el matcher {fuzzy}")
    print(f"  sospechosos             {report.suspect}")
    if fuzzy:
        print(f"\nTASA DE ERROR sobre los difusos: {report.suspect / fuzzy * 100:.2f}%")
        print(f"TASA DE ERROR sobre el total:    {report.error_rate:.2f}%")

    if report.by_category:
        print("\npor categoría:")
        for name, count in report.by_category.most_common():
            print(f"  {name:<22} {count}")

    for finding in report.examples[: args.show]:
        print(f"\n  [{finding.category}] {finding.detail}")
        print(f"    {finding.product_name[:70]}")
        print(f"    → {finding.catalog_name[:70]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
