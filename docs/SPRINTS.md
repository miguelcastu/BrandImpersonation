# Sprint plan

Each sprint ends with a working CLI path, focused tests, documentation, and a review before the next sprint begins. Keep providers optional and the pipeline usable offline with fixtures.

| Sprint | Scope | Reviewable result | Status |
| --- | --- | --- | --- |
| 1 — Discovery | Brand config, seed file, CT search, normalization, official-domain exclusion, SQLite sightings, CLI, CI | Discover and list candidate domains with source provenance | Complete; Sprint 2 authorized |
| 2 — Collection | Browser-assisted seed workflow and opt-in Playwright Chromium visit; rendered DOM text, title, forms, links, screenshot and fetch metadata; per-host limits | Local evidence for selected candidates, including JavaScript-rendered pages | Implemented; awaiting review |
| 3 — Typosquatting and enrichment | Bounded variants from the brand name/keywords, CT searches that retain variant matches; free current DNS and RDAP lookups; optional passive DNS only if a suitable free interface exists | Discover spelling variants and attach technical context | Planned |
| 4 — Automated page analysis and scoring | Analyze every saved page using brand, rendered text, form and link signals, Sprint 3 enrichment, and local screenshot OCR when needed; versioned weighted rules and conservative labels | Run one command to classify collected pages with a factor breakdown, without opening every screenshot | Planned |
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
- Collection starts only with the explicit `collect` command. Scoring and report actions remain planned.
- No credential collection, login submission, takedown request, or automated report to third parties is in scope.

## Sprint 2 acceptance criteria

- A real Chromium run on the bundled offline fixture captures content added by JavaScript.
- Evidence contains structured DOM data and a viewport screenshot, without a stored HTML dump.
- Existing candidates remain intact; each collection attempt adds a separate history entry.
- Failed, blocked, timed-out and HTTP-error visits remain visible as outcomes.
- Collection preserves an explicit URL's path; by default it visits up to five stored hostnames over HTTPS.
- Unit and browser integration tests run in CI without visiting external websites.
- See [the Sprint 2 walkthrough](sprints/02-collection.md) and [ADR 0002](adr/0002-rendered-browser-evidence.md).

## Sprint 3: planned typosquatting behavior

Given the configured brand (for example `Microsoft` / keyword `microsoft`), generate a small,
deterministic set of spelling variants automatically. Include character substitutions such as
`o -> 0` (`micr0soft`, `micros0ft`), `i -> 1`, `l -> 1`, and `s -> 5`, plus a single deletion
or adjacent-character swap. Unicode lookalike generation is outside the first implementation.

Cap generation at 20 unique variants and external CT searches at 10 per run, with a local preview
option. Keep the original search terms and track which variant matched. Candidate filtering must
recognize generated variants: otherwise `micr0soft` would be discarded by today's literal
`microsoft` rule. Continue excluding configured official domains.

Tests will verify the expected substitutions, deduplication, query caps, official-domain exclusion,
and that a CT fixture containing `micr0soft` survives filtering. Generated strings are hypotheses;
only observed hostnames become discovered candidates. This feature is planned, not active in Sprint 2.

## Sprint 4: planned automatic page analysis

`analyze` will read the saved collection evidence for each candidate and score it automatically.
Rules will use brand mentions in the title and rendered text, credential form fields, form action
destinations, link destinations, redirects, typosquatting matches and available DNS/RDAP context.
The score must include the evidence and contribution of each rule, so a reviewer can understand why
a page was prioritized. Scoring all collected pages will not require opening their screenshots.

When rendered DOM text is sparse, local OCR of the saved screenshot will add text evidence. The
planned OCR engine is [Tesseract](https://tesseract-ocr.github.io/tessdoc/), which runs locally and
is free. Its installation will be documented in that sprint. If OCR is unavailable or collection
failed, the result must say `insufficient_evidence`; it must not silently label the page safe.
Screenshots will remain available as supporting evidence for cases that are escalated.

Acceptance tests will include a JavaScript-rendered mock login page, a screenshot-only page, a
benign page that mentions Microsoft, a page with an external credential form action, and a failed
collection. The automated analysis should prioritize convincing impersonation signals while
explaining benign and uncertain outcomes. These are triage decisions, not a guarantee of confirmed
impersonation. Sprint 5 will export the ranked cases for optional review; no takedown submission is
planned.
