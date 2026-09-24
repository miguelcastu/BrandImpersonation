# Sprint 2: Collection

The pipeline can now move from a discovered hostname to local browser evidence. Collection is
explicit: `discover` never opens a candidate's website.

## Install and run the offline demo

```shell
uv sync --locked --extra dev --extra browser
uv run playwright install chromium
uv run brandwatch --db data/demo.db collect --demo
uv run brandwatch --db data/demo.db evidence
```

The demo registers `microsoft-login.example` with source `demo`, serves a local fixture to Chromium,
and captures a form and text inserted by JavaScript. No public site is visited. Its evidence is
marked `is_demo: true`; it is not a real impersonation finding. Open the JSON and PNG paths printed
by the command. The demo requires the browser installation, but runs offline after installation.

## Collect a real candidate

1. Run discovery and inspect `uv run brandwatch list`.
2. Use an exact URL for one of those hostnames:

   ```shell
   uv run brandwatch collect --url https://CANDIDATE-HOST/path
   uv run brandwatch evidence
   ```

Replace `CANDIDATE-HOST` with a hostname already in your database. `--url` can be repeated. With no
URL, `collect --limit 5` visits the HTTPS root of the first five stored hostnames in alphabetical
order. Reserved `.example` seed names do not resolve on the internet; use `--demo` for those samples.

For browser-assisted discovery, search manually in your browser, copy candidate URLs into a seed
file, then run `discover --source file --input your-seeds.txt`. Seed discovery currently stores only
hostnames. Pass the original URL to `collect --url` to keep its path. Automated search-engine scraping
is not part of this sprint.

## What is saved

Each visit creates `data/evidence/<unique-id>/evidence.json` and, when capture succeeds,
`screenshot.png`. SQLite records the attempt, status and JSON location in `collections`.

The JSON includes the requested/final URL, HTTP redirects, HTTP status, start/end times, errors, blocked-request
samples, collection settings, title, rendered text, links and form metadata. It excludes raw HTML,
input values and browser cookies. It records only the main document, with an iframe count.

Statuses are `ok`, `http_error`, `blocked`, `timeout` and `error`. An HTTP 404 page can still have
useful evidence. Failed visits get a JSON record even when no screenshot is possible. A batch
continues after an individual failure and returns exit code 1 if any visit did not finish with `ok`.

Default limits: five URLs per invocation (maximum 25), 15 seconds per visit plus context cleanup,
one second for rendering, 100 HTTP requests, 20,000 text characters, 100 links, 20 forms and 20 fields
per form. Text/link/form truncation is flagged. A viewport screenshot prevents extremely tall pages
from creating unbounded image dimensions.

Top-level HTTP redirects are followed as new checked navigations, up to five hops. Subresource HTTP
redirects are blocked. Responses over 8 MB are rejected after fetching; this does not bound bytes
downloaded. These restrictions can affect how faithfully some real sites render.

## Review and verification

```shell
uv run ruff check .
uv run pytest -q -m "not browser"
uv run pytest -q -m browser
```

The browser tests use real Chromium with local fixtures, including a JavaScript-generated form,
blocked private requests and redirects, a 404 response and a slow page. They verify that error
records are retained and the next page can still be collected. CI installs Chromium and runs both
test groups. Live third-party page rendering is not a deterministic test and is not a CI gate.

Local review evidence (2026-09-24): all 34 tests and Ruff passed, the offline demo produced its JSON
and PNG, and a manual collection of `https://example.com/` returned `ok` with title `Example Domain`.
The built wheel contains both packaged resources (`demo.html` and `dom.js`). Generated evidence
remains under ignored `data/` directories.

Typosquatting generation is scheduled for Sprint 3; current discovery still uses the literal
keywords and CT queries configured in the TOML file.
