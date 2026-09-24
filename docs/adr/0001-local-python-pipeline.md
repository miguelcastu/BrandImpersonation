# ADR 0001: Local Python pipeline with explicit evidence stages

**Status:** Accepted for Sprint 1
**Date:** 2026-09-24

## Context

This is a small learning project that should be free to run, easy to inspect, and able to produce local results without a hosted backend. Discovery, collection, enrichment, scoring, and action have different evidence and failure modes. A hostname match alone must not be presented as a confirmed impersonation.

## Decision

Use a Python CLI and SQLite file. Keep the discovery core in the standard library: TOML for brand scope, `urllib` for public CT queries, and `sqlite3` for candidates and sightings. Accept manual seed files so the demo and tests work without external services. Add Playwright only in Sprint 2 for rendered DOM collection, since it adds a browser download. Store evidence and scoring separately in later sprints. The action stage will only write local artifacts and support an explicit `no action` decision.

Use focused unit tests and GitHub Actions. Keep third-party providers optional, bounded by timeouts and response limits, and make source failures visible.

## Consequences

- A new contributor needs only Python 3.12 or uv for Sprint 1.
- Local SQLite keeps setup and operating cost at zero, but is intended for one user on one machine.
- CT search may be unavailable or return a large/incomplete response. Seed-file discovery remains usable.
- An explicit official-domain list avoids silent ownership guesses, but it must be maintained for each brand.
- Later sprints can evolve the schema without creating a cloud service.
