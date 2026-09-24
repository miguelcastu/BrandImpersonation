# ADR 0005: local-only action reports

## Status

Accepted for Sprint 5.

## Decision

Turn the latest explainable analysis records into local JSON or CSV case reports. Map `high_priority`, `review` and `insufficient_evidence` to a local `review` decision. Map `low_signal` to `no_action`. Store each generated decision in an append-only SQLite `actions` table.

The action stage has no network submission capability. It does not send takedown requests, email, credentials or reports to third parties. Report fields are limited to identifiers, scores, factors, provenance, evidence paths and a compact technical context summary.

## Rationale

The project needs a reviewable end-to-end result without introducing provider accounts, legal workflows or irreversible actions. A stable JSON schema supports later automation, while CSV makes the same cases easy to inspect in a spreadsheet. Keeping decisions local makes the demo safe to repeat.

## Consequences

Reports can become stale as new collection and analysis runs are added; each report records its generation time and decisions are kept as history. `no_action` means the current rules found low signal, not that the site is safe. `review` remains required for uncertainty and high-priority signals. Sprint 5 does not replace a human or an authorized external reporting process.
