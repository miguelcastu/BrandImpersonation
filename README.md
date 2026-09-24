# BrandWatch Lab

A small, free-first project for finding and reviewing possible brand impersonation. The pipeline is **discovery → collection → enrichment → scoring → action**. A discovered domain is only a lead; no stage treats a name match as proof of impersonation. The action stage will generate local review artifacts and never submit takedown requests.

Sprints 1 through 3 implement discovery from seed files and [crt.sh](https://crt.sh/), bounded typo variants, candidate provenance, SQLite storage, DNS/RDAP enrichment, and explicit Playwright collection of rendered page evidence. The CLI includes an offline browser demo, unit tests and browser integration tests in CI. Later work includes automatic page analysis in Sprint 4, so collected screenshots do not need to be opened one by one for initial triage. The acceptance criteria are in [docs/SPRINTS.md](docs/SPRINTS.md). Decisions are recorded in [ADR 0001](docs/adr/0001-local-python-pipeline.md), [ADR 0002](docs/adr/0002-rendered-browser-evidence.md), and [ADR 0003](docs/adr/0003-bounded-typos-and-enrichment.md).

## Run the offline example

Install [uv](https://docs.astral.sh/uv/) and run from the repository root:

```shell
uv sync --locked --extra dev
uv run brandwatch discover --source file --input examples/seeds.txt
uv run brandwatch list
uv run pytest -q
uv run ruff check .
```

The example uses Microsoft as the monitored brand and reserved `.example` domains as sample candidates. It does not claim those names are live or malicious. The output should contain `microsoft-account.example` and `microsoft-support.example`; the official Microsoft subdomain and unrelated domain are filtered out.

## Try certificate transparency discovery

```shell
uv run brandwatch discover --source ct
uv run brandwatch list
```

The example config is [config/brand.example.toml](config/brand.example.toml). For your own scope, copy that file and pass `--config path/to/brand.toml`. `keywords` determine which hostnames are candidates, `legitimate_domains` excludes known official domains and their subdomains, and `ct_queries` limits the public certificate searches. You can set a different database with `--db path/to/file.db` before the subcommand.

crt.sh is a public third-party service and may be slow, unavailable, or return no results. The CLI uses a 20-second timeout per query and rejects responses above 4 MB. A certificate record says a name appeared in a certificate; it does not establish that the site is reachable or deceptive. The official-domain list is illustrative and not a complete inventory of Microsoft properties. Review it before interpreting real results.

## Repository layout

```text
config/              Example brand scope
docs/                Sprint plan and architecture decisions
examples/            Offline seed data
src/brandwatch/       CLI, discovery, filtering, SQLite persistence
tests/               Unit and CLI tests
.github/workflows/    Lint and test CI
```

Local results live under `data/` and are ignored by Git.

## Preview typos and enrich candidates (Sprint 3)

```shell
uv run brandwatch variants --limit 10
uv run brandwatch discover --source file --input examples/seeds.txt
uv run brandwatch matches
uv run brandwatch enrich --limit 5
uv run brandwatch context
```

Generated typo strings are bounded hypotheses, not findings. CT discovery keeps configured search
terms first and performs at most ten external queries per run. `matches` records which keyword or
variant matched each observed hostname. Enrichment operates only on stored candidates and keeps
append-only DNS/RDAP snapshots; partial failures remain visible. See
[the Sprint 3 walkthrough](docs/sprints/03-typos-enrichment.md).

## Collect rendered browser evidence (Sprint 2)

```shell
uv sync --locked --extra dev --extra browser
uv run playwright install chromium
uv run brandwatch --db data/demo.db collect --demo
uv run brandwatch --db data/demo.db evidence
```

This demo renders a bundled page in Chromium without visiting public websites. It saves structured
DOM data and a screenshot under `data/evidence/`, with a history entry in the separate demo database.
The page inserts its text and form using JavaScript, so the output demonstrates browser rendering.

For real candidates already in your discovery database:

```shell
uv run brandwatch collect --url https://CANDIDATE-HOST/path
uv run brandwatch evidence
```

Replace `CANDIDATE-HOST` with an actual stored hostname. With no URL,
`collect --limit 5` selects five stored candidates. Collection records errors and continues through
the selected batch. It does not submit forms, fill credentials or crawl discovered links.

See [the Sprint 2 walkthrough](docs/sprints/02-collection.md) for the evidence format, limits and
browser-assisted seed workflow. After browser installation, run `uv run pytest -q` to include the
offline Chromium integration tests; `uv run pytest -q -m "not browser"` runs the unit tests alone.
