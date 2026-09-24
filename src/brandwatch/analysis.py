"""Explainable, conservative analysis of saved browser evidence."""

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from uuid import uuid4

from brandwatch.config import BrandConfig
from brandwatch.typos import brand_terms

RULE_VERSION = "sprint4-v1"
MAX_OCR_SECONDS = 20


@dataclass
class AnalysisResult:
    id: str
    collection_id: str
    hostname: str
    analyzed_at: str
    score: int
    label: str
    rule_version: str = RULE_VERSION
    factors: list[dict] = field(default_factory=list)
    ocr_used: bool = False
    error: str | None = None


def _factor(name: str, points: int, explanation: str) -> dict:
    return {"name": name, "points": points, "explanation": explanation}


def _text(value: object) -> str:
    return value.lower() if isinstance(value, str) else ""


def _external(url: str, hostname: str) -> bool:
    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    return bool(host and host != hostname and not host.endswith("." + hostname))


def _contains_brand(text: str, config: BrandConfig) -> str | None:
    for term in (config.name.lower(), *brand_terms(config)):
        if term and term in text:
            return term
    return None


def score_evidence(
    evidence: dict,
    config: BrandConfig,
    *,
    discovery_matches: list[tuple] | None = None,
    enrichment: dict | None = None,
    ocr_text: str = "",
) -> AnalysisResult:
    """Score one evidence JSON object and retain every rule contribution."""
    hostname = str(evidence.get("hostname", ""))
    factors: list[dict] = []
    dom = evidence.get("dom") if isinstance(evidence.get("dom"), dict) else {}
    title = _text(dom.get("title"))
    rendered_text = _text(dom.get("text"))
    body_text = rendered_text or _text(ocr_text)
    forms = dom.get("forms") if isinstance(dom.get("forms"), list) else []
    links = dom.get("links") if isinstance(dom.get("links"), list) else []
    requested_url = str(evidence.get("requested_url", ""))

    title_match = _contains_brand(title, config)
    if title_match:
        factors.append(_factor("brand_in_title", 1, f"title contains '{title_match}'"))
    body_match = _contains_brand(body_text, config)
    if body_match:
        factors.append(
            _factor("brand_in_rendered_text", 1, f"rendered text contains '{body_match}'")
        )

    credential_fields = []
    credential_forms = []
    for form in forms:
        if not isinstance(form, dict):
            continue
        fields = form.get("fields") if isinstance(form.get("fields"), list) else []
        sensitive = [
            field
            for field in fields
            if isinstance(field, dict)
            and (
                _text(field.get("type")) in {"password", "email"}
                or any(
                    token in _text(field.get("name"))
                    for token in ("user", "login", "pass", "email")
                )
            )
        ]
        if sensitive:
            credential_forms.append(form)
            credential_fields.extend(sensitive)
    if credential_fields:
        factors.append(
            _factor(
                "credential_fields",
                3,
                f"{len(credential_fields)} password/email/login-like field(s) detected",
            )
        )
    external_actions = [
        form
        for form in credential_forms
        if isinstance(form.get("action"), str)
        and _external(urljoin(requested_url, form["action"]), hostname)
    ]
    if external_actions:
        factors.append(
            _factor(
                "external_credential_action",
                4,
                f"{len(external_actions)} credential form action(s) leave the candidate host",
            )
        )

    external_links = [
        link
        for link in links
        if isinstance(link, dict)
        and isinstance(link.get("url"), str)
        and _external(urljoin(requested_url, link["url"]), hostname)
    ]
    if external_links:
        factors.append(
            _factor("external_links", 1, f"{len(external_links)} link destination(s) are external"))

    redirects = evidence.get("redirects") if isinstance(evidence.get("redirects"), list) else []
    if redirects:
        factors.append(_factor("redirects", 1, f"{len(redirects)} checked redirect(s)"))

    typo_matches = [
        row for row in (discovery_matches or []) if len(row) >= 5 and row[4] == "variant"
    ]
    if typo_matches:
        terms = sorted({str(row[3]) for row in typo_matches})
        factors.append(_factor("typosquatting_match", 2, f"matched variant(s): {', '.join(terms)}"))

    if enrichment:
        dns = enrichment.get("dns") if isinstance(enrichment.get("dns"), dict) else {}
        if dns.get("ipv4") or dns.get("ipv6"):
            factors.append(
                _factor("dns_resolves", 1, "candidate had current DNS addresses (context only)")
            )
        if enrichment.get("rdap"):
            factors.append(_factor("rdap_context", 0, "technical RDAP context is available"))

    score = sum(item["points"] for item in factors)
    collection_status = evidence.get("status")
    sparse = not title and not rendered_text and not forms and not links
    ocr_used = bool(ocr_text)
    if collection_status != "ok" or (sparse and not ocr_used):
        label = "insufficient_evidence"
    elif score >= 8:
        label = "high_priority"
    elif score >= 4:
        label = "review"
    else:
        label = "low_signal"
    return AnalysisResult(
        id=uuid4().hex,
        collection_id=str(evidence.get("id", "")),
        hostname=hostname,
        analyzed_at=datetime.now(UTC).isoformat(),
        score=score,
        label=label,
        factors=factors,
        ocr_used=ocr_used,
    )


def ocr_screenshot(path: str, *, command: str = "tesseract") -> str:
    """Run optional local Tesseract OCR; an unavailable OCR engine returns empty text."""
    executable = shutil.which(command)
    if not executable or not Path(path).is_file():
        return ""
    try:
        completed = subprocess.run(
            [executable, path, "stdout", "--quiet"],
            capture_output=True,
            text=True,
            timeout=MAX_OCR_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return completed.stdout[:20000] if completed.returncode == 0 else ""


def analyze_evidence_file(
    path: str, config: BrandConfig, *, discovery_matches=None, enrichment=None, use_ocr=False
) -> AnalysisResult:
    """Read one saved evidence file and analyze it without requiring a browser."""
    try:
        evidence = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(evidence, dict):
            raise ValueError("evidence JSON must be an object")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return AnalysisResult(
            id=uuid4().hex,
            collection_id="",
            hostname="",
            analyzed_at=datetime.now(UTC).isoformat(),
            score=0,
            label="insufficient_evidence",
            error=str(exc),
        )
    dom = evidence.get("dom") if isinstance(evidence.get("dom"), dict) else {}
    sparse = (
        not dom.get("title")
        and not dom.get("text")
        and not dom.get("forms")
        and not dom.get("links")
    )
    ocr_text = ""
    if use_ocr and sparse and evidence.get("screenshot_path"):
        ocr_text = ocr_screenshot(str(evidence["screenshot_path"]))
    return score_evidence(
        evidence,
        config,
        discovery_matches=discovery_matches,
        enrichment=enrichment,
        ocr_text=ocr_text,
    )
