"""Free discovery sources. Results are leads, not verified impersonation."""

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from brandwatch.config import BrandConfig
from brandwatch.hosts import normalize_hostname
from brandwatch.typos import TypoVariant, generate_variants

MAX_RESPONSE_BYTES = 4_000_000
MAX_CT_QUERIES = 10


class DiscoveryError(Exception):
    """A discovery source could not be read safely."""


@dataclass(frozen=True)
class CandidateFinding:
    hostname: str
    matched_term: str
    match_kind: str
    search_term: str


@dataclass(frozen=True)
class CTQuery:
    term: str
    kind: str


def _is_official(host: str, official: tuple[str, ...]) -> bool:
    return any(host == domain or host.endswith("." + domain) for domain in official)


def candidate_terms(
    config: BrandConfig, variants: tuple[TypoVariant, ...] | None = None
) -> tuple[tuple[str, str], ...]:
    variants = variants if variants is not None else generate_variants(config)
    terms = [(term, "keyword") for term in config.keywords]
    terms.extend((variant.value, "variant") for variant in variants)
    return tuple(terms)


def match_candidate(
    host: str, config: BrandConfig, variants: tuple[TypoVariant, ...] | None = None
) -> tuple[tuple[str, str], ...]:
    """Return every configured keyword/variant present in a non-official hostname."""
    if _is_official(host, config.legitimate_domains):
        return ()
    literal_matches = tuple((term, "keyword") for term in config.keywords if term in host)
    if literal_matches:
        return literal_matches
    return tuple(
        (term, kind)
        for term, kind in candidate_terms(config, variants)
        if kind == "variant" and term in host
    )


def filter_candidate_findings(
    values: list[str],
    config: BrandConfig,
    *,
    search_term: str = "local",
    variants: tuple[TypoVariant, ...] | None = None,
) -> tuple[CandidateFinding, ...]:
    findings = set()
    for value in values:
        host = normalize_hostname(value)
        if not host:
            continue
        for matched_term, match_kind in match_candidate(host, config, variants):
            findings.add(
                CandidateFinding(
                    hostname=host,
                    matched_term=matched_term,
                    match_kind=match_kind,
                    search_term=search_term,
                )
            )
    return tuple(
        sorted(findings, key=lambda item: (item.hostname, item.matched_term, item.search_term))
    )


def filter_candidates(values: list[str], config: BrandConfig) -> set[str]:
    """Compatibility wrapper returning only candidate hostnames."""
    return {finding.hostname for finding in filter_candidate_findings(values, config)}


def read_seed_findings(path: Path, config: BrandConfig) -> tuple[CandidateFinding, ...]:
    values = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    return filter_candidate_findings(values, config, search_term="seed-file")


def read_seed_file(path: Path, config: BrandConfig) -> set[str]:
    return {finding.hostname for finding in read_seed_findings(path, config)}


def _ct_values(records: object) -> list[str]:
    if not isinstance(records, list):
        raise DiscoveryError("crt.sh returned an unexpected JSON shape")
    values = []
    for record in records:
        if isinstance(record, dict):
            for field in ("name_value", "common_name"):
                names = record.get(field)
                if isinstance(names, str):
                    values.extend(names.splitlines())
    return values


def parse_ct_findings(
    records: object, config: BrandConfig, *, search_term: str = "ct-fixture"
) -> tuple[CandidateFinding, ...]:
    return filter_candidate_findings(_ct_values(records), config, search_term=search_term)


def parse_ct_records(records: object, config: BrandConfig) -> set[str]:
    return {finding.hostname for finding in parse_ct_findings(records, config)}


def build_ct_query_plan(
    config: BrandConfig, max_queries: int = MAX_CT_QUERIES
) -> tuple[CTQuery, ...]:
    """Keep configured CT terms first, then add typo hypotheses up to a hard query cap."""
    if not 1 <= max_queries <= MAX_CT_QUERIES:
        raise ValueError(f"CT query limit must be between 1 and {MAX_CT_QUERIES}")
    queries = []
    seen = set()
    for term in config.ct_queries:
        if term not in seen:
            seen.add(term)
            queries.append(CTQuery(term=term, kind="configured"))
        if len(queries) >= max_queries:
            return tuple(queries)
    for variant in generate_variants(config):
        if variant.value not in seen:
            seen.add(variant.value)
            queries.append(CTQuery(term=variant.value, kind="variant"))
        if len(queries) >= max_queries:
            break
    return tuple(queries)


def _fetch_crtsh(term: str, timeout: int) -> object:
    query = urlencode({"q": f"%{term}%", "output": "json"})
    request = Request(
        f"https://crt.sh/?{query}",
        headers={"User-Agent": "brandwatch-lab/0.3 (research project)"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read(MAX_RESPONSE_BYTES + 1)
        if len(payload) > MAX_RESPONSE_BYTES:
            raise DiscoveryError("crt.sh response exceeds 4 MB; use a narrower keyword")
        return json.loads(payload)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DiscoveryError(f"crt.sh query failed for {term}: {exc}") from exc


def search_crtsh_findings(
    config: BrandConfig, timeout: int = 20, max_queries: int = MAX_CT_QUERIES
) -> tuple[CandidateFinding, ...]:
    """Search bounded configured and typo terms and retain query/match provenance."""
    findings = set()
    for query in build_ct_query_plan(config, max_queries=max_queries):
        records = _fetch_crtsh(query.term, timeout)
        query_findings = parse_ct_findings(records, config, search_term=query.term)
        if query.kind == "variant":
            query_findings = tuple(
                finding
                for finding in query_findings
                if finding.match_kind == "variant" and finding.matched_term == query.term
            )
        findings.update(query_findings)
    return tuple(
        sorted(findings, key=lambda item: (item.hostname, item.matched_term, item.search_term))
    )


def search_crtsh(config: BrandConfig, timeout: int = 20) -> set[str]:
    """Compatibility wrapper preserving Sprint 1 configured-query behavior."""
    return {
        finding.hostname
        for finding in search_crtsh_findings(
            config, timeout=timeout, max_queries=min(len(config.ct_queries), MAX_CT_QUERIES)
        )
    }
