# Sprint 3: Typosquatting and enrichment

Sprint 3 expands discovery beyond literal brand strings while keeping the search bounded and
explainable. It also adds current DNS/RDAP context for candidates already in SQLite.

## Preview typo hypotheses offline

```shell
uv run brandwatch variants
uv run brandwatch variants --limit 10
```

For the example Microsoft scope this includes hypotheses such as `m1crosoft`, `micr0soft`,
`micro5oft` and `micros0ft`, plus single deletions and adjacent swaps. Generation is deterministic,
deduplicated and capped at 20 by default. These strings are not findings by themselves.

## Discover typo candidates

Seed-file discovery now recognizes generated variants automatically:

```shell
printf "micr0soft-login.example\n" > data/typo-seeds.txt
uv run brandwatch discover --source file --input data/typo-seeds.txt
uv run brandwatch matches
```

`matches` shows the source, search term, matched term and whether the match was a configured `keyword`
or generated `variant`. Known official domains and subdomains remain excluded.

CT discovery retains the configured `ct_queries` first and then uses typo hypotheses, with at most ten
external searches per invocation:

```shell
uv run brandwatch discover --source ct
uv run brandwatch discover --source ct --ct-limit 5
```

crt.sh is still an optional, best-effort public source. A generated query only discovers names that
actually appear in returned certificate records.

## Add technical context

```shell
uv run brandwatch enrich --limit 5
uv run brandwatch enrich --host micr0soft-login.example
uv run brandwatch context
```

Enrichment is restricted to stored candidates. Each run saves an append-only snapshot containing
current IPv4/IPv6 resolution from the local system resolver and selected technical RDAP fields from
`rdap.org`. DNS and RDAP failures are independent: a partial result is retained instead of discarding
successful context. RDAP contact/vCard data is not stored.

## Verification

```shell
uv run ruff check .
uv run pytest -q -m "not browser"
uv run pytest -q -m browser
```

Sprint 3 unit tests cover deterministic/capped generation, required substitutions, deletion/swap,
official-domain exclusion, CT query caps, variant provenance, append-only enrichment, partial failures
and CLI behavior. Browser tests remain the Sprint 2 offline fixtures because Sprint 3 does not change
browser collection.

## Deliberate limits

- No Unicode lookalikes, keyboard-neighbor generation or multi-edit combinations.
- DNS enrichment is A/AAAA resolution through the system resolver, not passive DNS history.
- No passive DNS provider is enabled until a stable free interface is selected explicitly.
- RDAP is public third-party data and can be incomplete or unavailable; absence is not a safety signal.
