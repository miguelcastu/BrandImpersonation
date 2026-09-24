# Sprint plan

Each sprint ends with a working CLI path, focused tests, documentation, and a review before the next sprint begins. Providers stay optional and the pipeline remains usable offline with fixtures.

| Sprint | Scope | Reviewable result | Status |
| --- | --- | --- | --- |
| 1 - Discovery | Brand config, seed file, CT search, normalization, official-domain exclusion, SQLite sightings, CLI, CI | Discover and list candidate domains with source provenance | Complete |
| 2 - Collection | Playwright visit, rendered DOM text, title, forms, links, screenshot and fetch metadata | Local evidence for selected candidates, including JavaScript-rendered pages | Complete |
| 3 - Typosquatting and enrichment | Bounded variants, CT match provenance, current DNS and RDAP lookups | Discover spelling variants and attach technical context | Implemented |
| 4 - Automated page analysis and scoring | Analyze saved evidence with explainable weighted rules and optional local OCR | Classify collected pages with a factor breakdown without opening every screenshot | Implemented; awaiting review |
| 5 - Action | Local case report and JSON/CSV export with no external submission | Review package and end-to-end demo | Planned |

## Sprint 1

- `uv sync --locked --extra dev` installs a fresh clone.
- The offline Microsoft example yields two candidates and excludes its official subdomain and unrelated host.
- Repeated discovery is idempotent and retains which source found each host.
- CT errors are reported clearly and unit tests use fixtures rather than network calls.
- GitHub Actions runs lint and tests on pushes and pull requests.

## Sprint 2

- Chromium on the bundled offline fixture captures content added by JavaScript.
- Evidence contains structured DOM text, title, forms, links, metadata and a screenshot without a stored HTML dump.
- Existing candidates remain intact; each collection attempt adds a separate history entry.
- Failed, blocked, timed-out and HTTP-error visits remain visible as outcomes.
- Collection preserves explicit URL paths and visits at most five stored hosts by default.
- Unit and browser tests run in CI without visiting external websites.

See [the Sprint 2 walkthrough](sprints/02-collection.md) and [ADR 0002](adr/0002-rendered-browser-evidence.md).

## Sprint 3: typosquatting and enrichment

The local generator creates substitutions (`o` to `0`, `i` to `1`, `l` to `1`, `s` to `5`), single deletions and adjacent swaps. It returns at most 20 unique variants. `brandwatch variants` previews them without network access.

CT discovery keeps configured queries first and adds generated variants up to 10 external queries. File discovery uses the same matching logic offline. The `discovery_matches` table records the source, search term, matched term and `keyword` or `variant` kind. Only observed hostnames become candidates, and official domains remain excluded.

`brandwatch enrich` operates only on stored candidates. It saves current IPv4/IPv6 resolution from the local resolver and selected technical RDAP fields in append-only SQLite snapshots. DNS and RDAP failures are independent. Passive DNS is not enabled because it needs a suitable historical provider.

## Sprint 4: automatic page analysis and scoring

`brandwatch analyze` reads saved `evidence.json` files and never needs to open screenshots for normal DOM analysis. The versioned rules record a point contribution and an explanation for every signal:

- brand text in the title: 1 point;
- brand text in rendered body text: 1 point;
- password, email or login-like fields: 3 points;
- credential form action on another host: 4 points;
- external links: 1 point;
- checked redirects: 1 point;
- a generated typo match: 2 points;
- current DNS resolution: 1 contextual point;
- RDAP availability: 0 points, retained as context only.

Scores of 8 or more are `high_priority`, scores from 4 to 7 are `review`, and lower scores are `low_signal`. A failed collection, or a successful collection with no usable DOM data and no OCR text, is always `insufficient_evidence`; it is never silently marked safe. These labels prioritize review and do not confirm impersonation.

`--ocr` enables a local Tesseract subprocess only when the DOM is sparse. If Tesseract is not installed or fails, the analysis keeps `insufficient_evidence` where appropriate. The `analyses` table stores the score, label, rule version and JSON factor breakdown as an append-only history.

Example:

```shell
uv run brandwatch --db data/demo.db collect --demo
uv run brandwatch --db data/demo.db analyze --config config/brand.example.toml --ocr
uv run brandwatch --db data/demo.db analyses
```

See [the Sprint 4 walkthrough](sprints/04-analysis-scoring.md) and [ADR 0004](adr/0004-explainable-scoring.md).

## Deliberate limits

- CT searches and typo generation are incomplete and can produce false leads.
- DNS/RDAP context and a score are not ownership or maliciousness proof.
- OCR is optional, local and dependent on an installed Tesseract executable.
- No credential collection, login submission, takedown request or automated third-party report is in scope.
