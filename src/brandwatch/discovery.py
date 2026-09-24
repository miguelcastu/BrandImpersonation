"""Free discovery sources. Results are leads, not verified impersonation."""

import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from brandwatch.config import BrandConfig
from brandwatch.hosts import is_candidate, normalize_hostname

MAX_RESPONSE_BYTES = 4_000_000


class DiscoveryError(Exception):
    """A discovery source could not be read safely."""


def filter_candidates(values: list[str], config: BrandConfig) -> set[str]:
    candidates = set()
    for value in values:
        host = normalize_hostname(value)
        if host and is_candidate(host, config.keywords, config.legitimate_domains):
            candidates.add(host)
    return candidates


def read_seed_file(path: Path, config: BrandConfig) -> set[str]:
    values = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    return filter_candidates(values, config)


def parse_ct_records(records: object, config: BrandConfig) -> set[str]:
    if not isinstance(records, list):
        raise DiscoveryError("crt.sh returned an unexpected JSON shape")
    values = []
    for record in records:
        if isinstance(record, dict):
            for field in ("name_value", "common_name"):
                names = record.get(field)
                if isinstance(names, str):
                    values.extend(names.splitlines())
    return filter_candidates(values, config)


def search_crtsh(config: BrandConfig, timeout: int = 20) -> set[str]:
    """Search crt.sh's public JSON output for each brand keyword."""
    candidates = set()
    for keyword in config.ct_queries:
        query = urlencode({"q": f"%{keyword}%", "output": "json"})
        request = Request(
            f"https://crt.sh/?{query}",
            headers={"User-Agent": "brandwatch-lab/0.1 (research project)"},
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = response.read(MAX_RESPONSE_BYTES + 1)
            if len(payload) > MAX_RESPONSE_BYTES:
                raise DiscoveryError("crt.sh response exceeds 4 MB; use a narrower keyword")
            records = json.loads(payload)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise DiscoveryError(f"crt.sh query failed for {keyword}: {exc}") from exc
        candidates.update(parse_ct_records(records, config))
    return candidates
