# Sprint plan

Each sprint ends with a working CLI path, focused tests, documentation, and a review before the next sprint begins. Keep providers optional and the pipeline usable offline with fixtures.

| Sprint | Scope | Reviewable result | Status |
| --- | --- | --- | --- |
| 1 — Discovery | Brand config, seed file, CT search, normalization, official-domain exclusion, SQLite sightings, CLI, CI | Discover and list candidate domains with source provenance | Implemented; awaiting review |
| 2 — Collection | Browser-assisted seed capture and opt-in Playwright Chromium visit; rendered DOM text, title, forms, links, screenshot and fetch metadata; per-host limits | Local evidence for selected candidates, including JavaScript-rendered pages | Planned |
| 3 — Enrichment | Free current DNS and RDAP lookups; optional passive DNS source only if a suitable free interface is available; record missing and failed lookups explicitly | Explainable technical context beside each candidate | Planned |
| 4 — Scoring | Versioned weighted rules for brand similarity, page evidence, and technical context; conservative labels | Reproducible score with factor breakdown and tests | Planned |
| 5 — Action | Local case report, JSON/CSV export, `no action` and `review` decisions; no external submission | Review package and end-to-end demo | Planned |

## Sprint 1 acceptance criteria

- A fresh clone can install with `uv sync --locked --extra dev`, run `uv run pytest -q` and `uv run ruff check .`.
- The offline Microsoft example yields two candidates and excludes its official subdomain and the unrelated host.
- Repeated discovery is idempotent and retains which source found each host.
- CT errors are reported clearly, and unit tests use fixtures rather than network calls.
- GitHub Actions runs lint and tests on pushes and pull requests.

## Deliberate limits

- CT substring queries are a small, imperfect discovery source. Search results can be incomplete or delayed.
- Discovery uses an explicit official-domain list rather than attempting to infer domain ownership.
- No collection, scoring, or external action is implemented until its sprint is reviewed.
- No credential collection, login submission, takedown request, or automated report to third parties is in scope.
