"""Identity key for products that have no registry and no barcode.

Medicines are identified against the ISP registry: ingredient + strength + form
is a key somebody else already curated. Cosmetics, hygiene and baby care have
neither — Chile publishes no cosmetics registry, and only 7% of the cosmetics we
scrape carry an EAN. For those, identity has to be *derived* from what the
storefronts themselves publish.

What they do publish is a brand (99% of the non-medicine listings carry one) and
a size in the title. That is the whole basis of the key here:

    brand + normalised size + the distinctive words of the title

Measured over the 25.031 non-medicine listings in production, this groups 759
products across two or more chains — against the 15 that barcodes alone manage
for cosmetics today.

**Why every distinctive word stays in the key.** The first draft kept only three
of them and collapsed `Vogue Esmalte Efecto Gel Jaguar 14ml` with `…Flamingo`
and `…Resiliencia`: three different nail polishes priced as one product. In
cosmetics the variant *is* the identity — the shade, the fragrance, the skin
type — and there is no way to tell a variant word from a filler word ahead of
time. So the key keeps them all and only drops words that describe the *offer*
rather than the product.

The trade is deliberate: this key under-groups rather than over-groups. Two
listings of the same product written very differently stay apart, which costs a
comparison. Two different products never merge, which would cost a wrong price.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

SIZE_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(ml|l|lt|litros?|g|gr|grs|kg|mg|oz|un|u|unidades?|"
    r"caps?|c[aá]psulas?|comprimidos?|pa[ñn]ales?|toallitas?)\b",
    re.I,
)

# Words that describe the *offer*, not the product. Two listings of the same
# shampoo routinely differ by these, so keeping them would split real groups.
_OFFER_NOISE = frozenset(
    {
        "pack", "oferta", "promo", "promocion", "combo", "set", "kit", "estuche",
        "edicion", "limitada", "gratis", "regalo", "nuevo", "nueva", "descuento",
        "ahorro", "precio", "especial", "exclusivo", "unidad", "unidades",
        "producto", "articulo", "gramos", "mililitros",
    }
)

# Units and connectives: they carry no identity once the size is parsed out.
_STOPWORDS = frozenset(
    {
        "con", "sin", "para", "por", "los", "las", "del", "que", "una", "uno",
        "mas", "ml", "gr", "grs", "cc", "lt", "und", "kit",
    }
)

NOISE = _OFFER_NOISE | _STOPWORDS


def fold(value: str | None) -> str:
    """Lowercase and strip accents, so `Tri-óleos` matches `Tri-Oleos`."""
    stripped = unicodedata.normalize("NFKD", value or "")
    return "".join(c for c in stripped if not unicodedata.combining(c)).lower()


def normalise_size(name: str | None) -> str:
    """Canonical pack size, or `""` when the title declares none.

    Litres and kilos fold into millilitres and grams so `1L` and `1000ml` — the
    same bottle written two ways by two chains — produce one key.
    """
    match = SIZE_RE.search(fold(name))
    if not match:
        return ""
    raw, unit = match.group(1).replace(",", "."), match.group(2).lower()
    try:
        number = float(raw)
    except ValueError:
        return ""
    if number <= 0:
        return ""

    if unit in {"l", "lt", "litro", "litros"}:
        number, unit = number * 1000, "ml"
    elif unit == "kg":
        number, unit = number * 1000, "g"
    elif unit in {"gr", "grs"}:
        unit = "g"
    elif unit in {"u", "un", "unidad", "unidades"}:
        unit = "un"
    elif unit.startswith("cap") or unit.startswith("cáps"):
        unit = "un"
    elif unit.startswith("pa"):  # pañal / pañales
        unit = "un"
    return f"{number:g}{unit}"


def distinctive_words(name: str | None, brand: str | None) -> tuple[str, ...]:
    """The words that identify the product, sorted so word order stops mattering.

    Brand words are dropped because the brand is already a field of the key;
    repeating it would let `Dove Dove Shampoo` and `Dove Shampoo` disagree.
    Bare numbers go too — they are the size, which is parsed separately — but
    alphanumerics like `310f` stay, because that is how shades are written.
    """
    brand_words = set(fold(brand).split())
    # Strip the size expressions first. `1000ml` written without a space is one
    # alphanumeric token, so it survived as a "distinctive word" while the same
    # bottle written `1L` produced none — the same product, two different keys.
    # Size is already a field of its own, so it has no business here.
    without_size = SIZE_RE.sub(" ", fold(name))
    return tuple(
        sorted(
            {
                word
                for word in re.findall(r"[a-z0-9]+", without_size)
                if word not in NOISE
                and word not in brand_words
                and not word.isdigit()
                and len(word) > 2
            }
        )
    )


@dataclass(frozen=True)
class DerivedIdentity:
    brand: str
    size: str
    words: tuple[str, ...]

    @property
    def is_groupable(self) -> bool:
        """Whether there is enough evidence to risk grouping on this key.

        A brand alone is not identity — `Dove` covers hundreds of products. A
        size alone is not either. Requiring brand, a size and at least two
        distinctive words is what keeps `Dove Shampoo 400ml` from swallowing
        every Dove shampoo of that size.
        """
        return bool(self.brand) and bool(self.size) and len(self.words) >= 2

    @property
    def key(self) -> str:
        return f"{self.brand}|{self.size}|{'-'.join(self.words)}"

    @classmethod
    def from_listing(cls, name: str | None, brand: str | None) -> "DerivedIdentity":
        return cls(
            brand=fold(brand).strip(),
            size=normalise_size(name),
            words=distinctive_words(name, brand),
        )
