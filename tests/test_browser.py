"""Real Chromium integration tests; every page response is an offline fixture."""

import asyncio
import json
from contextlib import closing
from pathlib import Path

import pytest

from brandwatch.cli import main
from brandwatch.collection import CollectionSettings, collect_urls
from brandwatch.storage import connect, list_collections

playwright_api = pytest.importorskip("playwright.async_api")
pytestmark = pytest.mark.browser


def test_demo_renders_javascript_and_saves_evidence(tmp_path):
    database = tmp_path / "demo.db"
    assert (
        main(["--db", str(database), "collect", "--demo", "--output", str(tmp_path / "evidence")])
        == 0
    )
    with closing(connect(database)) as db:
        rows = list_collections(db)
        assert len(rows) == 1
        assert rows[0][2] == "ok"
        evidence = json.loads(Path(rows[0][3]).read_text(encoding="utf-8"))
        assert evidence["is_demo"] is True
        assert evidence["http_status"] == 200
        assert evidence["dom"]["title"] == "Microsoft example - local demo"
        assert "added by JavaScript" in evidence["dom"]["text"]
        assert evidence["dom"]["forms"][0]["method"] == "POST"
        assert evidence["dom"]["forms"][0]["fields"][1]["type"] == "password"
        assert "value" not in evidence["dom"]["forms"][0]["fields"][1]
        assert Path(evidence["screenshot_path"]).read_bytes().startswith(b"\x89PNG")
        assert not list(tmp_path.rglob("*.html"))


def test_browser_redirects_requests_errors_and_limits_are_recorded(monkeypatch, tmp_path):
    # Resolve fixture names to a public IP for the guard, but fulfill all requests below.
    async def resolve(host):
        return {"93.184.216.34"} if host.endswith(".example") else {host}

    monkeypatch.setattr("brandwatch.network.resolve_addresses", resolve)
    requested = []
    html = """<title>Fixture</title><body><h1>Rendered evidence</h1>
      <img src="http://127.0.0.1/private">
      <script>
        fetch('/submit', {method: 'POST', body: 'test'}).catch(() => {});
        new WebSocket('wss://microsoft-login.example/socket');
      </script></body>"""

    class FixtureResponse:
        def __init__(self, body, status=200, headers=None):
            self.status = status
            self.headers = headers or {"content-type": "text/html"}
            self.content = body.encode()

        async def body(self):
            return self.content

        async def dispose(self):
            pass

    async def fixture_fetch(route, **kwargs):
        assert kwargs["max_redirects"] == 0
        url = route.request.url
        requested.append(url)
        if url.endswith("/redirect"):
            return FixtureResponse("", 302, {"location": "http://127.0.0.1/private"})
        elif url.endswith("/public-redirect"):
            return FixtureResponse("", 302, {"location": "/long"})
        elif url.endswith("/loop"):
            return FixtureResponse("", 302, {"location": "/loop"})
        elif url.endswith("/missing"):
            return FixtureResponse("<h1>Missing</h1>", 404)
        elif url.endswith("/slow"):
            await asyncio.sleep(6)
            return FixtureResponse("late")
        elif url.endswith("/long"):
            return FixtureResponse("<p>" + "x" * 25000)
        else:
            return FixtureResponse(html)

    monkeypatch.setattr(playwright_api.Route, "fetch", fixture_fetch)
    urls = [
        "https://microsoft-login.example" + path
        for path in ("/", "/redirect", "/missing", "/slow", "/long", "/public-redirect", "/loop")
    ]
    good, redirect, missing, slow, long, public_redirect, loop = asyncio.run(
        collect_urls(urls, tmp_path, CollectionSettings(timeout_ms=5000, render_wait_ms=200))
    )
    assert good.status == "ok"
    assert any("non-public" in item["reason"] for item in good.blocked_requests)
    assert any("GET and HEAD" in item["reason"] for item in good.blocked_requests)
    assert any("WebSocket" in item["reason"] for item in good.blocked_requests)
    assert redirect.status == "blocked"
    assert missing.status == "http_error" and missing.http_status == 404
    assert slow.status == "timeout"
    assert long.status == "ok" and long.dom["truncated"]["text"] is True
    assert public_redirect.status == "ok"
    assert public_redirect.final_url == "https://microsoft-login.example/long"
    assert public_redirect.redirects == [public_redirect.final_url]
    assert loop.status == "blocked" and "redirect limit" in loop.error
    assert len(long.dom["text"]) == 20000
    assert all("127.0.0.1" not in url and not url.endswith("/submit") for url in requested)
    assert all(Path(result.evidence_path).is_file() for result in (redirect, missing, slow))
