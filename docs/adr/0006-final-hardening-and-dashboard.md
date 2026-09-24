# ADR 0006: local dashboard and collection hardening

## Status

Accepted for the final improvement sprint.

## Decision

Keep the lab dependency-light and add a static local dashboard generated from the JSON report. Escape all report values, use a restrictive content security policy, and load no remote assets. Extend the bounded typo and scoring rules without changing the explainable factor model.

Refresh the collection DNS safety check for every request, reject local/metadata/reserved networks, keep Chromium's browser sandbox and fresh non-persistent contexts, and document VM/container and egress-firewall isolation as the required boundary for real untrusted pages. Treat application checks as defense in depth rather than a complete SSRF sandbox.

## Rationale

The project needs a useful final demo and a safe way to inspect results without a frontend build or third-party runtime. Rechecking DNS reduces stale-cache exposure, while OS-level isolation addresses the browser's independent DNS resolution and other TOCTOU races that application code cannot fully control.

## Consequences

The dashboard is intentionally small and read-only; it is not an account or case-management system. More typo and scoring signals can add false positives, so factors remain visible. Network safety depends on the host environment for production-grade guarantees. Historical enrichment snapshots are active observations, not passive DNS data.
