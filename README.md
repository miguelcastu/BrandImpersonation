# BrandWatch Lab

A small, free-first project for finding and reviewing possible brand impersonation. The pipeline is **discovery → collection → enrichment → scoring → action**. A discovered domain is only a lead; no stage treats a name match as proof of impersonation. The action stage will generate local review artifacts and never submit takedown requests.

Sprint 1 implements discovery from a seed file and [crt.sh](https://crt.sh/) certificate search, candidate filtering, SQLite storage, a CLI, unit tests, and CI. Later sprints are specified in [docs/SPRINTS.md](docs/SPRINTS.md). The design decision is recorded in [ADR 0001](docs/adr/0001-local-python-pipeline.md).

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
