# Architecture and investigation boundaries

[Overview](../README.md) · [Reviewer guide](reviewer-guide.md) · [Decisions](adr/)

The application is a local Python pipeline with SQLite history and optional
Playwright collection. It deliberately avoids services that are unnecessary for
a bounded investigation. See the [root pipeline diagram](../README.md).

| Stage | Source implementation | Input / durable result | Failure and scope |
| --- | --- | --- | --- |
| Configuration | `config.py`, `hosts.py` | TOML brand terms, official-domain exclusions and normalized ASCII hosts | Invalid scope fails; the sample official list is not a complete brand inventory. |
| Discovery | `discovery.py`, `typos.py` | Seed file or CT records → candidate and matched-term provenance | At most ten CT queries; timeout and response-size bounds. Typo strings are hypotheses, not findings. |
| Enrichment | `enrichment.py` | Stored candidates → append-only DNS/RDAP snapshots | Partial errors remain visible. Resolution and registration context are not maliciousness verdicts. |
| Collection | `collection.py`, `network.py` | Explicit stored URL or bundled demo → structured DOM, screenshot and error history | Bounded visits, fresh contexts, method/address checks; no form submission or link crawling. |
| Analysis | `analysis.py` | Saved observations → versioned score, factors, conservative label | Sparse/failed evidence stays `insufficient_evidence`; optional local Tesseract is a fallback, not a service. |
| Review reports | `reporting.py`, `storage.py` | Latest analyses → local JSON/CSV and decision history | Review or no_action only; `external_action_submitted` remains false. |

SQLite separates candidates, sightings, discovery matches, enrichment snapshots,
collections, analyses and action records. The case package links back to the
collection and analysis IDs and includes factor explanations without copying page
contents or contact data. See [local action reporting](sprints/05-action-report.md).

## Why evidence precedes scoring

The scorer reads saved observations so a reviewer can inspect the factors after
collection. Weights and labels are explicit in [ADR 0004](adr/0004-explainable-scoring.md):
brand text alone remains low signal; credential fields and destinations add
context; missing evidence never means safe. Thresholds are heuristic, not a
measured confidence probability. DNS contributes context; RDAP availability is
not proof of wrongdoing.

## Collection security limits

`RequestGuard` checks destinations before the browser fetches, blocks non-public
addresses and unsupported methods, and caps requests. The code explicitly labels
this as a **best-effort guard, not a network sandbox**: DNS is resolved separately
by the HTTP client, leaving a rebinding/time-of-check gap. The body-size rejection
also happens after the response is read, so it is not a transport-level memory
limit. Do not run it as a service with privileged network access or regard these
checks as complete isolation. Prefer the bundled no-network demo for review.

Public CT and DNS/RDAP workflows contact third parties and are optional. No public
candidate visits, enrichment requests or takedown submissions are needed to
understand or test the portfolio. Real collection needs deliberate scope and an
appropriately isolated environment. Browser observations can contain untrusted
content; keep generated data private and out of Git.
