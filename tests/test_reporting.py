import csv
import json
from contextlib import closing

from brandwatch.analysis import AnalysisResult
from brandwatch.cli import main
from brandwatch.collection import CollectionResult
from brandwatch.config import BrandConfig
from brandwatch.reporting import build_cases, build_report, recommended_decision, write_report
from brandwatch.storage import (
    connect,
    list_actions,
    save_analysis,
    save_candidates,
    save_collection,
)


def config() -> BrandConfig:
    return BrandConfig(
        name="Microsoft",
        keywords=("microsoft",),
        legitimate_domains=("microsoft.com",),
        ct_queries=("microsoft",),
    )


def analysis_row(hostname="micr0soft-login.example", label="high_priority"):
    return (
        "analysis-1",
        "collection-1",
        hostname,
        "2026-09-24T12:00:00+00:00",
        10,
        label,
        "sprint4-v1",
        json.dumps(
            {
                "factors": [{"name": "credential_fields", "points": 3, "explanation": "fields"}],
                "ocr_used": False,
            }
        ),
    )


def test_decisions_are_local_and_conservative():
    assert recommended_decision("low_signal") == "no_action"
    assert recommended_decision("high_priority") == "review"
    assert recommended_decision("insufficient_evidence") == "review"


def test_report_contains_factors_matches_and_safe_context_only(tmp_path):
    cases = build_cases(
        [analysis_row()],
        {"collection-1": ("ok", "evidence/evidence.json")},
        [("micr0soft-login.example", "ct", "micr0soft", "micr0soft", "variant")],
        {
            "micr0soft-login.example": (
                "ok",
                "2026-09-24T12:00:00+00:00",
                {"dns": {"ipv4": ["203.0.113.10"]}, "rdap": {"handle": "X"}},
            )
        },
    )
    document = build_report(config(), cases)
    output = tmp_path / "report.json"
    write_report(document, output, "json")
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["external_action_submitted"] is False
    assert saved["cases"][0]["recommended_decision"] == "review"
    assert saved["cases"][0]["discovery_matches"][0]["matched_term"] == "micr0soft"
    assert "passwordsecret" not in output.read_text(encoding="utf-8").lower()


def test_csv_export_has_stable_columns(tmp_path):
    document = build_report(
        config(), build_cases([analysis_row("safe.example", "low_signal")], {}, [], {})
    )
    output = tmp_path / "report.csv"
    write_report(document, output, "csv")
    with output.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["recommended_decision"] == "no_action"
    assert "factors_json" in rows[0]


def test_cli_report_writes_file_and_action_history(tmp_path, capsys):
    database = tmp_path / "results.db"
    evidence = tmp_path / "evidence.json"
    evidence.write_text(
        json.dumps(
            {
                "id": "collection-1",
                "hostname": "microsoft-help.example",
                "requested_url": "https://microsoft-help.example/",
                "status": "ok",
                "dom": {"title": "Help", "text": "Microsoft documentation"},
            }
        ),
        encoding="utf-8",
    )
    brand_file = tmp_path / "brand.toml"
    brand_file.write_text(
        'name = "Microsoft"\nkeywords = ["microsoft"]\n'
        'legitimate_domains = ["microsoft.com"]\n',
        encoding="utf-8",
    )
    with closing(connect(database)) as db:
        save_candidates(db, {"microsoft-help.example"}, "file")
        save_collection(
            db,
            CollectionResult(
                id="collection-1",
                hostname="microsoft-help.example",
                requested_url="https://microsoft-help.example/",
                started_at="2026-09-24",
                completed_at="2026-09-24",
                status="ok",
                evidence_path=str(evidence),
            ),
        )
        save_analysis(
            db,
            AnalysisResult(
                id="analysis-1",
                collection_id="collection-1",
                hostname="microsoft-help.example",
                analyzed_at="2026-09-24T12:00:00+00:00",
                score=1,
                label="low_signal",
                factors=[{"name": "brand_in_rendered_text", "points": 1, "explanation": "mention"}],
            ),
        )
    report_path = tmp_path / "cases.json"
    assert main(
        ["--db", str(database), "report", "--config", str(brand_file), "--output", str(report_path)]
    ) == 0
    assert "Wrote 1 case" in capsys.readouterr().out
    assert (
        json.loads(report_path.read_text(encoding="utf-8"))["cases"][0]["recommended_decision"]
        == "no_action"
    )
    with closing(connect(database)) as db:
        assert len(list_actions(db)) == 1
    assert main(["--db", str(database), "actions"]) == 0
    assert "no_action" in capsys.readouterr().out
