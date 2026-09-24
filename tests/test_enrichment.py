import io
import json
import socket
from contextlib import closing

from brandwatch.cli import main
from brandwatch.enrichment import EnrichmentResult, enrich_hostname, lookup_dns, lookup_rdap
from brandwatch.storage import connect, list_enrichments, save_candidates, save_enrichment


def test_dns_enrichment_sorts_and_separates_address_families(monkeypatch):
    def fake_getaddrinfo(host, port, type):
        assert host == "micr0soft-login.example"
        assert port is None
        assert type == socket.SOCK_STREAM
        return [
            (socket.AF_INET6, type, 6, "", ("2001:4860:4860::8888", 0, 0, 0)),
            (socket.AF_INET, type, 6, "", ("93.184.216.34", 0)),
            (socket.AF_INET, type, 6, "", ("93.184.216.34", 0)),
        ]

    monkeypatch.setattr("brandwatch.enrichment.socket.getaddrinfo", fake_getaddrinfo)
    assert lookup_dns("micr0soft-login.example") == {
        "ipv4": ["93.184.216.34"],
        "ipv6": ["2001:4860:4860::8888"],
    }


def test_rdap_keeps_technical_fields_and_drops_contact_data(monkeypatch):
    payload = {
        "handle": "EXAMPLE-1",
        "ldhName": "MICR0SOFT-LOGIN.EXAMPLE",
        "status": ["active"],
        "nameservers": [{"ldhName": "NS1.EXAMPLE"}],
        "events": [{"eventAction": "registration", "eventDate": "2026-09-20T00:00:00Z"}],
        "entities": [{"vcardArray": ["vcard", [["fn", {}, "text", "Private Person"]]]}],
    }

    def fake_urlopen(request, timeout):
        assert request.full_url.endswith("/micr0soft-login.example")
        assert timeout == 4
        return io.BytesIO(json.dumps(payload).encode())

    monkeypatch.setattr("brandwatch.enrichment.urlopen", fake_urlopen)
    result = lookup_rdap("micr0soft-login.example", timeout=4)
    assert result["handle"] == "EXAMPLE-1"
    assert result["nameservers"] == ["ns1.example"]
    assert result["events"][0]["action"] == "registration"
    assert "entities" not in result
    assert "Private Person" not in json.dumps(result)


def test_enrichment_retains_partial_result_when_rdap_fails(monkeypatch):
    monkeypatch.setattr(
        "brandwatch.enrichment.lookup_dns", lambda host: {"ipv4": ["93.184.216.34"], "ipv6": []}
    )

    def fail_rdap(host, timeout):
        raise OSError("offline")

    monkeypatch.setattr("brandwatch.enrichment.lookup_rdap", fail_rdap)
    result = enrich_hostname("micr0soft-login.example")
    assert result.status == "partial"
    assert result.dns["ipv4"] == ["93.184.216.34"]
    assert result.rdap == {}
    assert result.errors == ["rdap: offline"]


def test_enrichment_history_is_append_only(tmp_path):
    with closing(connect(tmp_path / "results.db")) as db:
        save_candidates(db, {"micr0soft-login.example"}, "file")
        for run_id, status in (("one", "ok"), ("two", "partial")):
            save_enrichment(
                db,
                EnrichmentResult(
                    id=run_id,
                    hostname="micr0soft-login.example",
                    collected_at=f"2026-09-24T12:00:0{len(run_id)}+00:00",
                    status=status,
                    dns={"ipv4": ["93.184.216.34"], "ipv6": []},
                    rdap={},
                ),
            )
        rows = list_enrichments(db)
        assert len(rows) == 2
        assert {row[3] for row in rows} == {"ok", "partial"}


def test_enrich_cli_only_operates_on_stored_candidates(monkeypatch, tmp_path, capsys):
    database = tmp_path / "results.db"
    with closing(connect(database)) as db:
        save_candidates(db, {"micr0soft-login.example"}, "file")

    monkeypatch.setattr(
        "brandwatch.cli.enrich_hostname",
        lambda host, timeout: EnrichmentResult(
            id="run",
            hostname=host,
            collected_at="2026-09-24T12:00:00+00:00",
            status="ok",
            dns={"ipv4": ["93.184.216.34"], "ipv6": []},
            rdap={"handle": "EXAMPLE"},
        ),
    )
    assert main(["--db", str(database), "enrich", "--host", "micr0soft-login.example"]) == 0
    assert "addresses=1" in capsys.readouterr().out
    assert main(["--db", str(database), "context"]) == 0
    assert "micr0soft-login.example" in capsys.readouterr().out
    assert main(["--db", str(database), "enrich", "--host", "unknown.example"]) == 1
    assert "Discover hostname" in capsys.readouterr().err
