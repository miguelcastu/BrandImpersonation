# Sprint 5 walkthrough: local action and reporting

Sprint 5 packages the scoring output as local cases. It is the action stage of the lab, but it deliberately stops at a review decision and a file on disk. It never submits a takedown, sends an email or contacts a provider.

## Run it

```shell
uv run brandwatch --db data/demo.db report --config config/brand.example.toml --output data/cases.json
uv run brandwatch --db data/demo.db report --format csv --output data/cases.csv
uv run brandwatch --db data/demo.db actions
```

The report command reads the latest analysis for each collection. `--limit` controls how many latest collection analyses are considered and `--decision review` or `--decision no_action` filters the exported cases. JSON is selected by default; the format can also be inferred from `.json` or `.csv` output names.

## Case contents

Each case contains:

- the analysis and collection identifiers;
- hostname, score, label and rule version;
- local recommendation: `review` or `no_action`;
- collection status and evidence path;
- scoring factors with explanations;
- discovery match provenance;
- a compact DNS/RDAP context summary.

The report does not copy rendered page text, screenshots, submitted values or RDAP contact data. Supporting evidence remains in the collection directory referenced by `evidence_path`. CSV keeps the nested fields as JSON strings so the file remains usable in a spreadsheet.

`review` is assigned to `high_priority`, `review` and `insufficient_evidence` labels. `no_action` is assigned only to `low_signal`. An uncertain or failed capture therefore remains visible for a human decision instead of being treated as safe.

The `actions` table records each local report decision with its analysis ID and output path. Re-running a report creates a new history row and does not delete earlier decisions.
