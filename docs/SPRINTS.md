# Sprint plan

Each sprint ends with a working CLI path, focused tests, documentation, and a review before the next sprint begins. Providers stay optional and the pipeline remains usable offline with fixtures.

| Sprint | Scope | Reviewable result | Status |
| --- | --- | --- | --- |
| 1 - Discovery | Brand config, seed file, CT search, normalization, official-domain exclusion, SQLite sightings, CLI, CI | Discover and list candidate domains with source provenance | Complete |
| 2 - Collection | Playwright visit, rendered DOM text, title, forms, links, screenshot and fetch metadata | Local evidence for selected candidates, including JavaScript-rendered pages | Complete |
| 3 - Typosquatting and enrichment | Bounded variants, CT match provenance, current DNS and RDAP lookups | Discover spelling variants and attach technical context | Complete |
| 4 - Automated page analysis and scoring | Analyze saved evidence with explainable weighted rules and optional local OCR | Classify collected pages with a factor breakdown without opening every screenshot | Complete |
| 5 - Action and reporting | Local case decisions plus JSON/CSV export; no external submission | Review package and end-to-end demo | Implemented; awaiting review |

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

`brandwatch analyze` reads saved `evidence.json` files and never needs to open screenshots for normal DOM analysis. Versioned rules record a point contribution and explanation for every signal: brand title (1), rendered text (1), credential fields (3), external credential action (4), external links (1), redirects (1), generated typo match (2), DNS resolution (1 contextual point), and RDAP availability (0 contextual points).

Scores of 8 or more are `high_priority`, scores from 4 to 7 are `review`, and lower scores are `low_signal`. A failed collection, or a successful collection with no usable DOM data and no OCR text, is always `insufficient_evidence`; it is never silently marked safe. These labels prioritize review and do not confirm impersonation.

`--ocr` enables a local Tesseract subprocess only when the DOM is sparse. The `analyses` table stores the score, label, rule version and JSON factor breakdown as append-only history.

## Sprint 5: local action and reporting

`brandwatch report` converts the latest analysis for each collection into a local case package. It assigns `review` to high-priority, review and insufficient-evidence cases. It assigns `no_action` only to low-signal cases. These are local workflow decisions; no command sends an email, takedown request or report to a provider.

JSON is the default format and includes the score, label, recommendation, collection status, evidence path, factors, discovery matches and a small DNS/RDAP summary. CSV is available for spreadsheets and excludes raw page content and contact data. Each report decision is recorded in the append-only `actions` table.

```shell
uv run brandwatch --db data/demo.db report --config config/brand.example.toml --output data/cases.json
uv run brandwatch --db data/demo.db report --format csv --output data/cases.csv
uv run brandwatch --db data/demo.db actions
```

See [the Sprint 5 walkthrough](sprints/05-action-report.md) and [ADR 0005](adr/0005-local-action-reporting.md).

## Deliberate limits

- CT searches, typo generation, DNS/RDAP context and scoring can be incomplete or produce false leads.
- A score and a report decision are not proof of ownership or maliciousness.
- OCR is optional, local and dependent on an installed Tesseract executable.
- No credential collection, login submission, takedown request or automated third-party report is in scope.
