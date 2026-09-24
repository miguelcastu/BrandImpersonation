# ADR 0002: Explicit browser visits with structured evidence

**Status:** Accepted for Sprint 2

**Date:** 2026-09-24

## Context

Candidate names do not show whether a page imitates a brand. Pages may render their forms and
content with JavaScript. The project needs evidence without storing complete source or DOM HTML,
and must remain runnable locally without paid services or Docker.

## Decision

Add Playwright Chromium as an optional dependency. A separate `collect` command performs sequential
visits in fresh, non-persistent contexts. It captures the main document's title, rendered body text,
link destinations, form actions and field metadata, plus a 1280 x 720 screenshot. The browser fetches
HTML to render the page, but the collector persists JSON and PNG files only. It does not read input
values, submit forms, or follow the links it discovers.

Store artifacts in a unique directory per attempt and index them in a new SQLite `collections`
table linked to `candidates`. Keep repeated visits and failures as separate history entries. Existing
Sprint 1 tables need no destructive migration. Explicit `--url` arguments preserve paths and query
strings and must belong to stored candidates; default visits use the HTTPS root of up to five hosts.

Use a total visit time budget, an explicit rendering wait, request-count limits and extraction caps.
Check HTTP request destinations for public addresses, including redirects and subresources. Block
non-GET/HEAD requests, media downloads, WebSockets and service workers, and enable Chromium's sandbox.
Maintain TLS certificate validation. Screenshots cover the viewport rather than an unbounded page.

Fetch intercepted HTTP requests with automatic redirects disabled. Follow up to five top-level
HTTP redirects as new, checked navigations; block subresource HTTP redirects. Reject responses over
8 MB after fetching. This is a response acceptance limit, not a download bandwidth or memory cap.

The offline demo fulfills a packaged fixture directly in Chromium and aborts other page requests.
Real-browser integration tests verify JavaScript rendering, evidence files, private-destination and
POST blocking, redirects, HTTP errors, timeouts and continued processing.

## Consequences and limits

- Browser installation is an extra step; discovery remains usable without Playwright.
- A fixed rendering wait may miss delayed content; callers can adjust it within bounds.
- Blocking requests may affect page fidelity; blocked-request samples are recorded in the evidence.
- This is one-page collection. Iframe contents, recursive crawling and authenticated pages are outside scope.
- Application-level DNS checks are best effort: Playwright's HTTP client resolves independently, so this is not a
  complete network sandbox or protection against DNS rebinding. Production isolation would require
  an enforced network boundary.
- Artifact files and SQLite are not one transaction; deleting or moving artifacts can break their
  stored paths. Keep them under the ignored local `data/` directory.

## References

- [Playwright browser contexts and request interception](https://playwright.dev/python/docs/api/class-browsercontext)
- [Playwright JavaScript evaluation](https://playwright.dev/python/docs/evaluating)
- [Playwright screenshots](https://playwright.dev/python/docs/screenshots)
