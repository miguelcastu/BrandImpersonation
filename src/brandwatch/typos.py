"""Deterministic, bounded typosquatting hypotheses for brand discovery."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from brandwatch.config import BrandConfig

SUBSTITUTIONS = {"o": "0", "i": "1", "l": "1", "s": "5"}


@dataclass(frozen=True)
class TypoVariant:
    value: str
    base: str
    rule: str


def brand_terms(config: "BrandConfig") -> tuple[str, ...]:
    """Return domain-safe configured terms that may seed typo generation."""
    terms = list(config.keywords)
    name = config.name.strip().lower()
    if name and name not in terms and name.isascii() and all(c.isalnum() or c == "-" for c in name):
        terms.append(name)
    return tuple(terms)


def generate_variants(config: "BrandConfig", limit: int = 20) -> tuple[TypoVariant, ...]:
    """Generate at most ``limit`` one-edit spelling variants in deterministic order."""
    if not 1 <= limit <= 100:
        raise ValueError("variant limit must be between 1 and 100")

    variants: list[TypoVariant] = []
    seen = set(brand_terms(config))

    def add(value: str, base: str, rule: str) -> None:
        if len(variants) >= limit or value in seen or not 3 <= len(value) <= 40:
            return
        seen.add(value)
        variants.append(TypoVariant(value=value, base=base, rule=rule))

    for base in brand_terms(config):
        for index, char in enumerate(base):
            replacement = SUBSTITUTIONS.get(char)
            if replacement:
                add(
                    base[:index] + replacement + base[index + 1 :],
                    base,
                    f"substitute:{char}->{replacement}@{index}",
                )
        for index in range(len(base)):
            add(base[:index] + base[index + 1 :], base, f"delete:{base[index]}@{index}")
        for index in range(len(base) - 1):
            if base[index] != base[index + 1]:
                add(
                    base[:index]
                    + base[index + 1]
                    + base[index]
                    + base[index + 2 :],
                    base,
                    f"swap:{index}-{index + 1}",
                )
        if len(variants) >= limit:
            break

    return tuple(variants)
