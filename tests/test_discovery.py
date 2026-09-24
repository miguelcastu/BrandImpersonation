import io
import json
from urllib.error import URLError

import pytest

from brandwatch.config import BrandConfig
from brandwatch.discovery import (
    DiscoveryError,
    filter_candidates,
    parse_ct_records,
    read_seed_file,
    search_crtsh,
)
from brandwatch.hosts import normalize_hostname


@pytest.fixture
def config():
    return BrandConfig(
        name="Microsoft",
        keywords=("microsoft",),
        legitimate_domains=("microsoft.com",),
        ct_queries=("microsoft-login",),
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://*.Microsoft-Account.Example/login", "microsoft-account.example"),
        ("MICROSOFT-SUPPORT.EXAMPLE.", "microsoft-support.example"),
        ("ftp://microsoft.example", None),
        ("http://[not-an-ip]/", None),
        ("https://127.0.0.1/", None),
        ("not a host", None),
    ],
)
def test_normalize_hostname(value, expected):
    assert normalize_hostname(value) == expected


def test_filter_excludes_official_subdomains_but_not_suffix_lookalikes(config):
    values = [
        "login.microsoft.com",
        "microsoft.com",
        "microsoft.com.example",
        "microsoft-account.example",
        "unrelated.example",
        "microsoft-account.example",
    ]
    assert filter_candidates(values, config) == {
        "microsoft.com.example",
        "microsoft-account.example",
    }


def test_ct_records_split_multiline_sans_and_deduplicate(config):
    records = [
        {"name_value": "*.microsoft-account.example\nlogin.microsoft.com"},
        {"common_name": "microsoft-account.example"},
        {"name_value": 17},
    ]
    assert parse_ct_records(records, config) == {"microsoft-account.example"}


def test_ct_rejects_unexpected_json(config):
    with pytest.raises(DiscoveryError, match="unexpected JSON shape"):
        parse_ct_records({"name_value": "microsoft.example"}, config)


def test_seed_file_ignores_comments_and_official_hosts(tmp_path, config):
    path = tmp_path / "seeds.txt"
    path.write_text("# comment\nlogin.microsoft.com\nmicrosoft-help.example\n", encoding="utf-8")
    assert read_seed_file(path, config) == {"microsoft-help.example"}


def test_ct_query_uses_targeted_term_and_parses_response(monkeypatch, config):
    payload = json.dumps([{"name_value": "microsoft-login.example"}]).encode()
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["timeout"] = timeout
        return io.BytesIO(payload)

    monkeypatch.setattr("brandwatch.discovery.urlopen", fake_urlopen)
    assert search_crtsh(config) == {"microsoft-login.example"}
    assert "microsoft-login" in seen["url"]
    assert "output=json" in seen["url"]
    assert seen["timeout"] == 20


def test_ct_network_error_is_visible(monkeypatch, config):
    def fail(*_args, **_kwargs):
        raise URLError("unavailable")

    monkeypatch.setattr("brandwatch.discovery.urlopen", fail)
    with pytest.raises(DiscoveryError, match="query failed"):
        search_crtsh(config)
