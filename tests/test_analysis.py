import json
from contextlib import closing

from brandwatch.analysis import analyze_evidence_file, score_evidence
from brandwatch.cli import main
from brandwatch.collection import CollectionResult
from brandwatch.config import BrandConfig
from brandwatch.storage import connect, save_candidates, save_collection


def brand() -> BrandConfig:
    return BrandConfig(
        name="Microsoft",
        keywords=("microsoft",),
        legitimate_domains=("microsoft.com",),
        ct_queries=("microsoft-login",),
    )


def test_high_priority_score_explains_credential_and_brand_signals():
    evidence = {
        "id": "collection-1",
        "hostname": "micr0soft-login.example",
        "requested_url": "https://micr0soft-login.example/",
        "status": "ok",
        "redirects": ["https://micr0soft-login.example/login"],
        "dom": {
            "title": "Microsoft account sign in",
            "text": "Microsoft secure account login",
            "forms": [
                {
                    "action": "https://collector.example/submit",
                    "fields": [
                        {"type": "email", "name": "email"},
                        {"type": "password", "name": "password"},
                    ],
                }
            ],
            "links": [{"url": "https://collector.example/privacy"}],
        },
    }
    result = score_evidence(
        evidence,
        brand(),
        discovery_matches=[
            ("micr0soft-login.example", "ct", "micr0soft", "micr0soft", "variant")
        ],
        enrichment={"dns": {"ipv4": ["203.0.113.10"]}, "rdap": {"handle": "X"}},
    )
    assert result.label == "high_priority"
    names = {factor["name"] for factor in result.factors}
    assert {
        "brand_in_title",
        "credential_fields",
        "external_credential_action",
        "typosquatting_match",
    } <= names
    assert all("points" in factor and "explanation" in factor for factor in result.factors)


def test_benign_brand_mention_is_low_signal():
    result = score_evidence(
        {
            "id": "collection-2",
            "hostname": "news.example",
            "status": "ok",
            "dom": {"title": "Technology news", "text": "Microsoft announced a new product."},
        },
        brand(),
    )
    assert result.label == "low_signal"
    assert result.score == 1


def test_sparse_dom_without_ocr_is_insufficient():
    result = score_evidence(
        {"id": "collection-3", "hostname": "empty.example", "status": "ok", "dom": {}}, brand()
    )
    assert result.label == "insufficient_evidence"


def test_failed_collection_is_never_labeled_safe():
    result = score_evidence(
        {
            "id": "collection-4",
            "hostname": "failed.example",
            "status": "timeout",
            "dom": {"title": "Microsoft", "text": "Microsoft"},
        },
        brand(),
    )
    assert result.label == "insufficient_evidence"


def test_optional_ocr_supplies_text_when_dom_is_sparse(monkeypatch, tmp_path):
    evidence = tmp_path / "screenshot-only.json"
    evidence.write_text(
        json.dumps(
            {
                "id": "collection-ocr",
                "hostname": "microsoft-image.example",
                "status": "ok",
                "screenshot_path": str(tmp_path / "screen.png"),
                "dom": {},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("brandwatch.analysis.ocr_screenshot", lambda _path: "Microsoft sign in")
    result = analyze_evidence_file(str(evidence), brand(), use_ocr=True)
    assert result.ocr_used is True
    assert result.label == "low_signal"


def test_cli_analyze_persists_explainable_result(tmp_path, capsys):
    database = tmp_path / "results.db"
    evidence = tmp_path / "evidence.json"
    evidence.write_text(
        json.dumps(
            {
                "id": "collection-5",
                "hostname": "microsoft-help.example",
                "requested_url": "https://microsoft-help.example/",
                "status": "ok",
                "dom": {"title": "Microsoft help", "text": "Microsoft documentation"},
            }
        ),
        encoding="utf-8",
    )
    config = tmp_path / "brand.toml"
    config.write_text(
        'name = "Microsoft"\nkeywords = ["microsoft"]\n'
        'legitimate_domains = ["microsoft.com"]\n',
        encoding="utf-8",
    )
    with closing(connect(database)) as db:
        save_candidates(db, {"microsoft-help.example"}, "file")
        save_collection(
            db,
            CollectionResult(
                id="collection-5",
                hostname="microsoft-help.example",
                requested_url="https://microsoft-help.example/",
                started_at="2026-09-24",
                completed_at="2026-09-24",
                status="ok",
                evidence_path=str(evidence),
            ),
        )
    assert main(["--db", str(database), "analyze", "--config", str(config)]) == 0
    assert "low_signal" in capsys.readouterr().out
    assert main(["--db", str(database), "analyses"]) == 0
    assert "sprint4-v1" in capsys.readouterr().out
