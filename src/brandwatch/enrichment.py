"""Free, bounded DNS and RDAP enrichment for already discovered candidates."""

import json
import socket
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import quote
from urllib.request import Request, urlopen
from uuid import uuid4

MAX_RDAP_BYTES = 1_000_000


@dataclass
class EnrichmentResult:
    id: str
    hostname: str
    collected_at: str
    status: str
    dns: dict = field(default_factory=dict)
    rdap: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def lookup_dns(hostname: str) -> dict:
    """Return current A/AAAA addresses using the system resolver."""
    entries = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    ipv4 = sorted({entry[4][0] for entry in entries if ":" not in entry[4][0]})
    ipv6 = sorted({entry[4][0] for entry in entries if ":" in entry[4][0]})
    return {"ipv4": ipv4, "ipv6": ipv6}


def _trim_rdap(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("RDAP returned an unexpected JSON shape")
    nameservers = []
    for item in payload.get("nameservers", []):
        if isinstance(item, dict) and isinstance(item.get("ldhName"), str):
            nameservers.append(item["ldhName"].lower())
    events = []
    for item in payload.get("events", []):
        if not isinstance(item, dict):
            continue
        action = item.get("eventAction")
        date = item.get("eventDate")
        if isinstance(action, str) and isinstance(date, str):
            events.append({"action": action, "date": date})
    statuses = payload.get("status", [])
    return {
        "handle": payload.get("handle") if isinstance(payload.get("handle"), str) else None,
        "ldh_name": payload.get("ldhName") if isinstance(payload.get("ldhName"), str) else None,
        "statuses": [item for item in statuses if isinstance(item, str)][:20]
        if isinstance(statuses, list)
        else [],
        "nameservers": sorted(set(nameservers))[:20],
        "events": events[:20],
    }


def lookup_rdap(hostname: str, timeout: int = 8) -> dict:
    """Query the public rdap.org bootstrap service and keep technical fields only."""
    request = Request(
        f"https://rdap.org/domain/{quote(hostname, safe='')}",
        headers={
            "Accept": "application/rdap+json, application/json",
            "User-Agent": "brandwatch-lab/0.3",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        payload = response.read(MAX_RDAP_BYTES + 1)
    if len(payload) > MAX_RDAP_BYTES:
        raise ValueError("RDAP response exceeds 1 MB")
    return _trim_rdap(json.loads(payload))


def enrich_hostname(hostname: str, timeout: int = 8) -> EnrichmentResult:
    """Collect DNS and RDAP independently so partial results remain useful."""
    result = EnrichmentResult(
        id=uuid4().hex,
        hostname=hostname,
        collected_at=datetime.now(UTC).isoformat(),
        status="error",
    )
    successes = 0
    try:
        result.dns = lookup_dns(hostname)
        successes += 1
    except OSError as exc:
        result.errors.append(f"dns: {exc}")

    try:
        result.rdap = lookup_rdap(hostname, timeout=timeout)
        successes += 1
    except (OSError, ValueError) as exc:
        result.errors.append(f"rdap: {exc}")

    result.status = "ok" if successes == 2 else "partial" if successes == 1 else "error"
    return result
