"""Small dependency-free local HTML view for a generated case report."""

# The generated HTML intentionally keeps compact CSS/JS lines; Python source linting
# should not force those presentation strings into unreadable fragments.
# ruff: noqa: E501

import html
import json
from pathlib import Path


def _safe(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def render_dashboard(document: dict) -> str:
    cases = document.get("cases") if isinstance(document.get("cases"), list) else []
    rows = []
    for case in cases:
        factors = case.get("factors") if isinstance(case.get("factors"), list) else []
        factor_text = "; ".join(
            f"{item.get('name', '')} ({item.get('points', 0)})"
            for item in factors
            if isinstance(item, dict)
        )
        rows.append(
            "<tr data-label='"
            + _safe(case.get("label"))
            + "'><td><code>"
            + _safe(case.get("hostname"))
            + "</code></td><td>"
            + _safe(case.get("score"))
            + "</td><td><span class='badge "
            + _safe(case.get("label"))
            + "'>"
            + _safe(case.get("label"))
            + "</span></td><td>"
            + _safe(case.get("recommended_decision"))
            + "</td><td>"
            + _safe(factor_text)
            + "</td></tr>"
        )
    row_html = "\n".join(rows) or "<tr><td colspan='5'>No cases in this report.</td></tr>"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'">
<title>BrandWatch local cases</title>
<style>
:root {{ color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; background:#101827; color:#e5edf8; }}
body {{ margin:0; }} main {{ max-width:1160px; margin:0 auto; padding:36px 24px; }}
.hero {{ display:flex; justify-content:space-between; gap:20px; align-items:end; margin-bottom:24px; }}
h1 {{ margin:0 0 8px; font-size:32px; }} p {{ color:#9fb0c8; }}
.card {{ background:#182438; border:1px solid #2d405d; border-radius:14px; padding:18px; box-shadow:0 12px 32px #05091255; }}
.controls {{ display:flex; gap:12px; align-items:center; margin-bottom:14px; }} select {{ background:#101827; color:#e5edf8; border:1px solid #385170; border-radius:8px; padding:8px; }}
table {{ width:100%; border-collapse:collapse; }} th,td {{ text-align:left; padding:13px 10px; border-bottom:1px solid #2d405d; vertical-align:top; }} th {{ color:#9fb0c8; font-size:12px; text-transform:uppercase; letter-spacing:.08em; }}
code {{ color:#8bd5ff; }} .badge {{ border-radius:99px; padding:4px 9px; font-size:12px; }} .high_priority {{ background:#7f1d1d; color:#fecaca; }} .review {{ background:#854d0e; color:#fef08a; }} .low_signal {{ background:#14532d; color:#bbf7d0; }} .insufficient_evidence {{ background:#374151; color:#e5e7eb; }}
small {{ color:#9fb0c8; }}
</style></head><body><main>
<section class="hero"><div><h1>BrandWatch local cases</h1><p>Brand: {_safe(document.get('brand'))} · Report {_safe(document.get('report_version'))}</p></div><small>No external action submitted</small></section>
<section class="card"><div class="controls"><label for="filter">Filter:</label><select id="filter"><option value="all">All cases</option><option value="high_priority">High priority</option><option value="review">Review</option><option value="low_signal">Low signal</option><option value="insufficient_evidence">Insufficient evidence</option></select></div>
<table><thead><tr><th>Hostname</th><th>Score</th><th>Label</th><th>Decision</th><th>Factors</th></tr></thead><tbody id="cases">{row_html}</tbody></table></section>
</main><script>document.getElementById('filter').addEventListener('change',function(e){{for(const row of document.querySelectorAll('#cases tr[data-label]'))row.hidden=e.target.value!=='all'&&row.dataset.label!==e.target.value;}});</script>
</body></html>
"""


def render_dashboard_file(input_path: Path, output_path: Path) -> None:
    document = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("report JSON must contain an object")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_dashboard(document), encoding="utf-8")
