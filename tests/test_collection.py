import asyncio
from contextlib import closing

import pytest

from brandwatch.cli import main, select_urls
from brandwatch.collection import CollectionResult, CollectionSettings
from brandwatch.network import RequestGuard, is_safe_public_address, validate_url
from brandwatch.storage import connect, list_collections, save_candidates, save_collection


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "javascript:alert(1)",
        "https://user:pass@site.example/",
        "http://site.example:8080/",
        "https://site.example/a b",
        "http://[broken/",
    ],
)
def test_invalid_collection_urls_are_rejected(url):
    with pytest.raises(ValueError):
        validate_url(url)


@pytest.mark.parametrize(
    "addresses",
    [
        {"127.0.0.1"},
        {"10.0.0.1"},
        {"169.254.169.254"},
        {"::1"},
        {"93.184.216.34", "192.168.0.1"},
        {"224.0.0.1"},
    ],
)
def test_guard_rejects_any_non_public_destination(monkeypatch, addresses):
    async def resolve(_):
        return addresses

    monkeypatch.setattr("brandwatch.network.resolve_addresses", resolve)
    assert "non-public" in asyncio.run(RequestGuard().check("https://site.example/"))


def test_guard_allows_public_get_but_blocks_posts_and_limits_requests(monkeypatch):
    async def resolve(_):
        return {"93.184.216.34"}

    monkeypatch.setattr("brandwatch.network.resolve_addresses", resolve)
    guard = RequestGuard(max_requests=2)
    assert asyncio.run(guard.check("https://site.example/")) is None
    assert "GET and HEAD" in asyncio.run(guard.check("https://site.example/", "POST"))
    assert "limit" in asyncio.run(guard.check("https://site.example/"))


def test_public_address_policy_rejects_internal_and_metadata_ranges():
    assert is_safe_public_address("93.184.216.34") is True
    assert is_safe_public_address("127.0.0.1") is False
    assert is_safe_public_address("169.254.169.254") is False
    assert is_safe_public_address("::1") is False


def test_guard_blocks_internal_hostname_before_dns(monkeypatch):
    async def fail_resolution(_):
        raise AssertionError("internal hostname should be rejected before DNS")

    monkeypatch.setattr("brandwatch.network.resolve_addresses", fail_resolution)
    assert "hostname blocked" in asyncio.run(RequestGuard().check("https://metadata.google.internal/"))


def test_selector_requires_discovery_and_preserves_url_path(tmp_path):
    with closing(connect(tmp_path / "results.db")) as db:
        save_candidates(db, {"microsoft-login.example"}, "file")
        url = "https://microsoft-login.example/account?lang=en"
        assert select_urls(db, [url, url], 5) == [url]
        assert select_urls(db, None, 1) == ["https://microsoft-login.example/"]
        with pytest.raises(ValueError, match="Discover hostname"):
            select_urls(db, ["https://other.example/"], 5)
        with pytest.raises(ValueError, match="Too many"):
            select_urls(db, [url, url + "#more"], 1)


def test_collection_settings_are_bounded():
    with pytest.raises(ValueError, match="timeout"):
        CollectionSettings(timeout_ms=0)
    with pytest.raises(ValueError, match="render wait"):
        CollectionSettings(timeout_ms=1000, render_wait_ms=2000)


def test_collection_history_keeps_success_and_failure(tmp_path):
    with closing(connect(tmp_path / "results.db")) as db:
        save_candidates(db, {"microsoft-login.example"}, "ct")
        for run_id, status in (("first", "ok"), ("second", "timeout")):
            save_collection(
                db,
                CollectionResult(
                    id=run_id,
                    hostname="microsoft-login.example",
                    requested_url="https://microsoft-login.example/",
                    started_at="2026-09-24",
                    status=status,
                    evidence_path=f"{run_id}/evidence.json",
                ),
            )
        rows = list_collections(db)
        assert {row[2] for row in rows} == {"ok", "timeout"}
        assert db.execute("SELECT count(*) FROM candidates").fetchone()[0] == 1


def test_collect_cli_persists_failure_and_returns_nonzero(monkeypatch, tmp_path, capsys):
    database = tmp_path / "results.db"
    with closing(connect(database)) as db:
        save_candidates(db, {"microsoft-login.example"}, "file")

    async def fake_collect(urls, output, settings, *, demo):
        assert urls == ["https://microsoft-login.example/account"]
        return [
            CollectionResult(
                id="failed",
                hostname="microsoft-login.example",
                requested_url=urls[0],
                started_at="2026-09-24",
                status="timeout",
                evidence_path="result/evidence.json",
            )
        ]

    monkeypatch.setattr("brandwatch.cli.collect_urls", fake_collect)
    assert (
        main(["--db", str(database), "collect", "--url", "https://microsoft-login.example/account"])
        == 1
    )
    assert "timeout" in capsys.readouterr().out
    assert main(["--db", str(database), "evidence"]) == 0
    assert "failed" in capsys.readouterr().out


def test_new_table_preserves_sprint_one_data(tmp_path):
    import sqlite3

    path = tmp_path / "sprint-one.db"
    with closing(sqlite3.connect(path)) as old:
        old.execute(
            "CREATE TABLE candidates (hostname TEXT PRIMARY KEY, first_seen TEXT, last_seen TEXT)"
        )
        old.execute("INSERT INTO candidates VALUES ('microsoft-login.example', 'first', 'last')")
        old.commit()
    with closing(connect(path)) as updated:
        assert updated.execute("SELECT * FROM candidates").fetchone() == (
            "microsoft-login.example",
            "first",
            "last",
        )
        assert list_collections(updated) == []
