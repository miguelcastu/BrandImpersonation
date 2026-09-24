# ADR 0003: Bounded typo discovery and local technical enrichment

**Status:** Accepted for Sprint 3

**Date:** 2026-09-24

## Context

Literal brand keywords miss common lookalike spellings such as `micr0soft`. Expanding every possible
edit would create noisy candidate sets and excessive third-party requests. Candidate names also need
basic technical context before later scoring, but the project must remain free-first and runnable
without new Python dependencies.

## Decision

Generate a deterministic global maximum of 20 one-edit variants from configured brand terms. Sprint 3
supports the substitutions `o -> 0`, `i -> 1`, `l -> 1` and `s -> 5`, plus one-character deletion and
adjacent-character swap. The original configured terms remain unchanged and generated strings are
hypotheses only: they do not become candidates until an observed hostname matches them.

`variants` previews the hypotheses without network access. CT discovery keeps configured `ct_queries`
first, adds generated variants after them and performs at most 10 crt.sh requests per invocation.
Discovery stores both the query term and the keyword/variant that matched a hostname. Existing Sprint 1
helpers keep their original return types for compatibility.

Add append-only enrichment snapshots for already discovered candidates. DNS enrichment uses the local
system resolver for current IPv4/IPv6 addresses. RDAP uses the public `rdap.org` bootstrap endpoint,
keeps only technical registration fields (status, nameservers and lifecycle events), caps responses at
1 MB and uses a bounded timeout. DNS and RDAP are independent so one can succeed when the other fails.
No contact/vCard entity data is persisted.

Do not add passive DNS in this sprint. The project has no selected anonymous, stable, free interface
whose availability and usage terms are suitable for a deterministic lab workflow.

## Consequences and limits

- The typo model is deliberately small and explainable; it does not attempt Unicode homographs,
  arbitrary edit distance, keyboard adjacency or combinatorial substitutions.
- A 20-variant/10-query cap controls noise and external requests but can miss relevant names.
- System DNS enrichment captures A/AAAA resolution, not a complete DNS zone view.
- RDAP may return no result for some subdomains or registries; that is stored as a partial/error result
  rather than interpreted as benign.
- Enrichment is historical and append-only, allowing later scoring to distinguish collection time.
