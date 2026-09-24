# Sprint 4 walkthrough: automatic analysis and scoring

Sprint 4 turns saved browser evidence into a review queue. It reads the structured DOM JSON produced by Sprint 2, joins discovery and enrichment context from SQLite, and writes an explainable analysis record.

## Run it

```shell
uv run brandwatch --db data/demo.db collect --demo
uv run brandwatch --db data/demo.db analyze --config config/brand.example.toml
uv run brandwatch --db data/demo.db analyses
```

Add `--ocr` when a page may contain text in an image or has sparse DOM text. The command looks for a local `tesseract` executable and uses it only for sparse evidence. No OCR dependency is required for the normal path.

`analyze` processes up to 25 collection records by default, with `--limit` allowing up to 100 and `--host` selecting stored hosts. It can analyze failed collection records too, preserving an `insufficient_evidence` result instead of hiding the failure.

## How a result is formed

The analyzer loads title, rendered text, forms, form fields, form actions, links, redirects and collection status. It checks the saved discovery matches for generated variants and uses the latest saved enrichment context for the hostname. Each applicable rule produces a factor with `name`, `points` and a plain-language `explanation`.

The score is deliberately conservative. A brand mention alone is a low signal. Credential fields and an external credential action carry the largest weights because they provide stronger triage evidence. DNS resolution contributes only one contextual point; RDAP availability contributes zero points. A score is a prioritization aid, not a takedown decision.

The labels are:

- `high_priority`: 8 or more points;
- `review`: 4-7 points;
- `low_signal`: fewer than 4 points with usable evidence;
- `insufficient_evidence`: collection failed or no usable DOM/OCR evidence exists.

The rule version is `sprint4-v1`, and analysis rows are append-only in SQLite. `analyses` prints the compact result; the factor JSON is retained in the database for later reporting in Sprint 5.

## OCR and limitations

Tesseract is invoked as a local subprocess with a 20-second limit and a 20,000-character cap. If it is unavailable, the analyzer does not infer that the page is benign. Screenshots remain supporting evidence for a reviewer and are not uploaded anywhere by this project.
