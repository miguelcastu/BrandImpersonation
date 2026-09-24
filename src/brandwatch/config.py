"""Configuration loading and validation."""

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from brandwatch.hosts import normalize_hostname

KEYWORD_PATTERN = re.compile(r"[a-z0-9-]{3,40}\Z")


@dataclass(frozen=True)
class BrandConfig:
    name: str
    keywords: tuple[str, ...]
    legitimate_domains: tuple[str, ...]
    ct_queries: tuple[str, ...]

    @classmethod
    def load(cls, path: Path) -> "BrandConfig":
        with path.open("rb") as config_file:
            raw = tomllib.load(config_file)
        name = raw.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name must be a non-empty string")
        keywords = raw.get("keywords")
        if not isinstance(keywords, list) or not keywords or not all(
            isinstance(item, str) and KEYWORD_PATTERN.fullmatch(item.lower())
            for item in keywords
        ):
            raise ValueError("keywords must be a non-empty list of domain-safe words (3-40 chars)")
        domains = raw.get("legitimate_domains")
        if not isinstance(domains, list) or not domains:
            raise ValueError("legitimate_domains must be a non-empty list")
        normalized = tuple(
            normalize_hostname(item) if isinstance(item, str) else None for item in domains
        )
        if any(domain is None for domain in normalized):
            raise ValueError("legitimate_domains must contain valid hostnames")
        queries = raw.get("ct_queries", keywords)
        if not isinstance(queries, list) or not queries or not all(
            isinstance(item, str) and KEYWORD_PATTERN.fullmatch(item.lower())
            for item in queries
        ):
            raise ValueError(
                "ct_queries must be a non-empty list of domain-safe words (3-40 chars)"
            )
        return cls(
            name=name.strip(),
            keywords=tuple(dict.fromkeys(item.lower() for item in keywords)),
            legitimate_domains=tuple(dict.fromkeys(normalized)),
            ct_queries=tuple(dict.fromkeys(item.lower() for item in queries)),
        )
