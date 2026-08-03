"""Price anomaly checks — quarantine wild swings before they hit the public ranking."""
from __future__ import annotations

import re
from dataclasses import dataclass


# Floor for a plausible OTC price in CLP (excluding free/placeholder).
MIN_PLAUSIBLE_CLP = 200

# Pharmacies here really do sell one needle, one tongue depressor or one alcohol
# swab, at prices the general floor rejects outright. Those products then have no
# price at all and never appear on the site — 24 of the 35 quarantined products
# in production were exactly this, and none of them had ever had an accepted
# price. A separate, much lower floor applies only when the name explicitly says
# the listing is a single unit.
MIN_SINGLE_UNIT_CLP = 15

# Deliberately narrow. A per-unit rule (price / pack_count) was tried first and
# rejected: `product_identity.extract_pack_count` reads volumes and doses as
# counts — "Shampoo x 750 ml" becomes 750 units, "Glaupax 500 XR x 30
# Comprimidos" becomes 500 — which would have quarantined 826 currently-good
# prices (1.1%). Matching an explicit single-unit phrase cannot do that, and
# because it only ever *lowers* a floor it cannot reject anything accepted today.
SINGLE_UNIT_RE = re.compile(
    # `ampolla` is deliberately absent. The words here name things that are
    # cheap *because* they are one disposable item — a needle, a tongue
    # depressor. An ampoule is just a container: `Solu-Cortef 100 mg x 1
    # Ampolla` and `Ácido Zoledrónico 4 mg/5 ml x 1 Ampolla` cost thousands, and
    # letting them drop to the 15 CLP floor would wave through a scraping error
    # on a drug's first observed price, when no previous price exists to compare
    # against. Removing it costs nothing: none of the 27 products this floor
    # currently rescues mentions an ampoule.
    r"(?:^|[\s(\-])1\s*(?:unidad(?:es)?|un\b|aguja|jeringa|paleta|baja\s*lenguas?|"
    r"bajalengua|tira|sobre|par|pieza|toallita)"
    r"|x\s*1\s*(?:unidad|un\b)"
    r"|\(\s*1\s*unidad\s*\)",
    re.IGNORECASE,
)

# Relative move vs last accepted price that triggers quarantine.
DROP_RATIO = 0.15   # new < 15% of last
JUMP_RATIO = 8.0    # new > 8× last


def price_floor(name: str | None) -> int:
    """Minimum plausible price for this listing, in CLP.

    Called by `check_price`. Without a name the answer is `MIN_PLAUSIBLE_CLP`,
    so a caller that has no name to give keeps the pre-existing behaviour.
    """
    if name and SINGLE_UNIT_RE.search(name):
        return MIN_SINGLE_UNIT_CLP
    return MIN_PLAUSIBLE_CLP


@dataclass(frozen=True)
class AnomalyVerdict:
    ok: bool
    reason: str | None = None

    @classmethod
    def accept(cls) -> AnomalyVerdict:
        return cls(ok=True)

    @classmethod
    def reject(cls, reason: str) -> AnomalyVerdict:
        return cls(ok=False, reason=reason)


def check_price(
    price: int, last_price: int | None, name: str | None = None
) -> AnomalyVerdict:
    """Decide whether `price` may enter the public price stream.

    `name` is optional and defaults to None, which yields exactly the previous
    behaviour (floor `MIN_PLAUSIBLE_CLP`). Pass it whenever the listing name is
    at hand: it is the only way the single-unit exception above can fire, and
    without it a 100 CLP needle is quarantined on every run, forever.
    """
    if price is None or price <= 0:
        return AnomalyVerdict.reject("non_positive")
    floor = price_floor(name)
    if price < floor:
        # Floor in the reason so the log says which rule rejected the row —
        # same shape as scheduler.evaluate_health's below_floor.
        return AnomalyVerdict.reject(f"below_floor:{price}<{floor}")

    if last_price and last_price > 0:
        if price < last_price * DROP_RATIO:
            return AnomalyVerdict.reject(
                f"drop:{last_price}->{price} (<{DROP_RATIO:.0%} of last)"
            )
        if price > last_price * JUMP_RATIO:
            return AnomalyVerdict.reject(
                f"jump:{last_price}->{price} (>{JUMP_RATIO:g}x last)"
            )
    return AnomalyVerdict.accept()
