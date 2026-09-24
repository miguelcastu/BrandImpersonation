"""Build local case reports from explainable analysis records."""

import csv
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from brandwatch.config import BrandConfig

REPORT_VERSION = "sprint5-v1"


def recommended_decision(label: str) -> str:
    """Return a local triage decision; this function never contacts a third party."""
    return "no_action" if label == "low_signal" else "review"


def _factor_summary(payload: dict) -> list[dict]:
    factors = payload.get("factors")
    return factors if isinstance(factors, list) else []


def build_cases(
    analysis_rows: Iterable[tuple],
    collection_by_id: dict[str, tuple[str, str]],
    matches: Iterable[tuple],
    enrichments: dict[str, tuple[str, str, dict]],
    decision_filter: str = "all",
) -> list[dict]:
    cases = []
    match_map: dict[str, list[dict]] = {}
    for row in matches:
        hostname, source, search_term, matched_term, match_kind = row
        match_map.setdefault(hostname, []).append(
            {
                "source": source,
                "search_term": search_term,
                "matched_term": matched_term,
                "match_kind": match_kind,
            }
        )
    for row in analysis_rows:
        (
            analysis_id,
            collection_id,
            hostname,
            analyzed_at,
            score,
            label,
            rule_version,
            data_json,
        ) = row
        decision = recommended_decision(label)
        if decision_filter != "all" and decision != decision_filter:
            continue
        try:
            payload = json.loads(data_json)
        except (TypeError, json.JSONDecodeError):
            payload = {}
        collection_status, evidence_path = collection_by_id.get(collection_id, ("unknown", ""))
        enrichment = enrichments.get(hostname)
        enrichment_summary = None
        if enrichment:
            enrichment_status, collected_at, enrichment_payload = enrichment
            dns = enrichment_payload.get("dns", {})
            addresses = len(dns.get("ipv4", [])) + len(dns.get("ipv6", []))
            enrichment_summary = {
                "status": enrichment_status,
                "collected_at": collected_at,
                "addresses": addresses,
                "rdap_available": bool(enrichment_payload.get("rdap")),
            }
        cases.append(
            {
                "case_id": analysis_id,
                "analysis_id": analysis_id,
                "collection_id": collection_id,
                "hostname": hostname,
                "analyzed_at": analyzed_at,
                "score": score,
                "label": label,
                "recommended_decision": decision,
                "rule_version": rule_version,
                "collection_status": collection_status,
                "evidence_path": evidence_path,
                "factors": _factor_summary(payload),
                "ocr_used": bool(payload.get("ocr_used")),
                "analysis_error": payload.get("error"),
                "discovery_matches": sorted(match_map.get(hostname, []), key=lambda item: (
                    item["matched_term"], item["search_term"]
                )),
                "enrichment": enrichment_summary,
            }
        )
    return cases


def build_report(brand: BrandConfig, cases: list[dict]) -> dict:
    return {
        "report_version": REPORT_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "brand": brand.name,
        "case_count": len(cases),
        "cases": cases,
        "external_action_submitted": False,
    }


def write_report(document: dict, path: Path, output_format: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "json":
        path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return
    if output_format != "csv":
        raise ValueError("report format must be json or csv")
    fields = [
        "case_id",
        "hostname",
        "score",
        "label",
        "recommended_decision",
        "collection_status",
        "evidence_path",
        "rule_version",
        "ocr_used",
        "factors_json",
        "discovery_matches_json",
        "enrichment_json",
    ]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for case in document["cases"]:
            writer.writerow(
                {
                    **{field: case.get(field, "") for field in fields[:9]},
                    "factors_json": json.dumps(case["factors"], ensure_ascii=False, sort_keys=True),
                    "discovery_matches_json": json.dumps(
                        case["discovery_matches"], ensure_ascii=False, sort_keys=True
                    ),
                    "enrichment_json": json.dumps(
                        case["enrichment"], ensure_ascii=False, sort_keys=True
                    ),
                }
            )
