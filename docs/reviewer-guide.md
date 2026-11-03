# Reviewer guide and offline demonstration

[Overview](../README.md) · [Architecture](architecture.md) · [ADRs](adr/)
· [Sprint acceptance](SPRINTS.md)

## Two-minute route

Read the pipeline diagram, then inspect `analysis.py` and the reporting rules.
The engineering question is how to retain discovery provenance and explain why
a lead deserves review without mistaking it for a confirmed impersonation.

## Start without a browser

From the repository root, with uv and Python 3.12+:

```shell
uv sync --locked --extra dev
uv run brandwatch --db data/reviewer-seeds.db discover --source file --input examples/seeds.txt
uv run brandwatch --db data/reviewer-seeds.db list
uv run brandwatch --db data/reviewer-seeds.db matches
uv run pytest -q -m "not browser"
uv run ruff check .
```

Expect the two reserved `.example` seed candidates described in the README.
This does not perform CT, DNS, RDAP or browser collection. Dependency installation
needs package access; application commands above run from bundled data.

## End-to-end browser evidence and report

Install the optional browser dependencies once; Chromium download needs network
access. The demo itself fulfills its bundled page locally and blocks all other
requests. Do not substitute a public URL.

```shell
uv sync --locked --extra dev --extra browser
uv run playwright install chromium
uv run brandwatch --db data/reviewer-demo.db collect --demo
uv run brandwatch --db data/reviewer-demo.db evidence
uv run brandwatch --db data/reviewer-demo.db analyze --config config/brand.example.toml
uv run brandwatch --db data/reviewer-demo.db analyses
uv run brandwatch --db data/reviewer-demo.db report --output data/reviewer-cases.json
uv run brandwatch --db data/reviewer-demo.db actions
uv run pytest -q -m browser
```

Inspect the evidence JSON and actual saved screenshot under `data/evidence/`;
their paths appear in collection output. Compare the analysis factors with the
local JSON report. IDs/timestamps vary by run, so no exact byte-for-byte output
is promised. No OCR installation is required for this rendered DOM demonstration.

## Test and failure review

- `test_discovery.py` / `test_typos.py`: exclusions, normalization and bounded candidates.
- `test_collection.py` / `test_browser.py`: selection, request restrictions, failure history and local rendering.
- `test_enrichment.py`: stored-candidate scope, partial results and append-only history.
- `test_analysis.py`: factor weights, weak/failed evidence and optional OCR behavior.
- `test_reporting.py` / `test_storage_cli.py`: provenance, stable fields, local decisions and CLI persistence.

[CI](../.github/workflows/ci.yml) separates unit and offline browser tests.
A missing browser executable is a setup failure, not a clean test result.
Generated SQLite databases, screenshots and reports remain ignored under `data/`.
To reset, close the application and remove only the deliberately selected demo
database and artifacts; preserve evidence you still need.

The repository URL remains `BrandImpersonation` to preserve existing links.
The product name is BrandWatch Lab. Renaming is deferred until external references
and integrations can be checked.
