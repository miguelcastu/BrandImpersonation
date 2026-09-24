# ADR 0004: explainable local page scoring

## Status

Accepted for Sprint 4.

## Decision

Analyze the structured rendered evidence already saved by Sprint 2. Use small versioned weighted rules for brand text, credential fields, credential destinations, external links, redirects, typo matches and technical context. Persist each factor, score and label in an append-only SQLite table.

Use conservative labels: `high_priority` at 8 points, `review` at 4-7 points, `low_signal` below 4 points, and `insufficient_evidence` when collection failed or both DOM and optional OCR evidence are empty. Permit local Tesseract OCR as an opt-in fallback for sparse DOM evidence, without making it a required Python dependency.

## Rationale

The project needs automatic triage so every screenshot does not need manual inspection, while keeping decisions reviewable. Structured DOM evidence is faster and easier to test than image-only analysis. A factor breakdown shows why a page was prioritized and lets later sprints export a case without hiding the underlying observations.

Technical context is kept subordinate to page behavior: DNS resolution adds one contextual point and RDAP availability adds no points. A brand mention alone remains low signal. Failed or sparse evidence is explicitly uncertain rather than labeled safe.

## Consequences

The rules are a triage aid and can produce false positives or miss sophisticated pages. OCR quality depends on a local Tesseract installation. Rule changes require a new rule version so results can be compared over time. Sprint 5 may export these local results, but no external action is automated.
