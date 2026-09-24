"""Host normalization and candidate selection."""

import ipaddress
import re
from urllib.parse import urlsplit

LABEL_PATTERN = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")


def normalize_hostname(value: str) -> str | None:
    """Return a safe ASCII hostname from a URL or bare host, or None."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or any(char.isspace() for char in value):
        return None
    try:
        if "://" in value:
            parsed = urlsplit(value)
            if parsed.scheme.lower() not in {"http", "https"}:
                return None
        else:
            parsed = urlsplit("//" + value)
        host = parsed.hostname
    except ValueError:
        return None
    if not host:
        return None
    host = host.removeprefix("*.").rstrip(".").lower()
    try:
        host = host.encode("idna").decode("ascii")
        ipaddress.ip_address(host)
    except ValueError:
        pass
    except UnicodeError:
        return None
    else:
        return None  # IP addresses are not domain candidates.
    if len(host) > 253 or len(host.split(".")) < 2:
        return None
    if not all(LABEL_PATTERN.fullmatch(label) for label in host.split(".")):
        return None
    return host


def is_candidate(host: str, keywords: tuple[str, ...], official: tuple[str, ...]) -> bool:
    if any(host == domain or host.endswith("." + domain) for domain in official):
        return False
    return any(keyword in host for keyword in keywords)
