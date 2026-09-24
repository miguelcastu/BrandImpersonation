import json

from brandwatch.cli import main
from brandwatch.dashboard import render_dashboard


def test_dashboard_escapes_report_values_and_has_local_csp():
    page = render_dashboard(
        {
            "brand": "Microsoft <demo>",
            "report_version": "sprint5-v1",
            "cases": [
                {
                    "hostname": "example.test",
                    "score": 4,
                    "label": "review",
                    "recommended_decision": "review",
                    "factors": [{"name": "brand", "points": 1}],
                }
            ],
        }
    )
    assert "Microsoft &lt;demo&gt;" in page
    assert "Content-Security-Policy" in page
    assert "https://" not in page
    assert "example.test" in page


def test_dashboard_cli_writes_html(tmp_path, capsys):
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps({"brand": "Microsoft", "report_version": "sprint5-v1", "cases": []}),
        encoding="utf-8",
    )
    output = tmp_path / "dashboard.html"
    assert main(["dashboard", "--input", str(report), "--output", str(output)]) == 0
    assert output.is_file()
    assert "Wrote local dashboard" in capsys.readouterr().out
