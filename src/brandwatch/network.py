"""Basic request restrictions for visiting untrusted public websites."""

import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit


def validate_url(url: str) -> str:
    """Validate a collection URL and return its hostname."""
    if len(url) > 2048 or any(char.isspace() or ord(char) < 32 for char in url):
        raise ValueError("URL must be at most 2048 characters without whitespace")
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Collection requires an http:// or https:// URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URLs containing credentials are not supported")
    if parsed.port not in {None, 80, 443}:
        raise ValueError("Collection only supports ports 80 and 443")
    return parsed.hostname.encode("idna").decode("ascii").lower().rstrip(".")


async def resolve_addresses(host: str) -> set[str]:
    entries = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
    return {entry[4][0] for entry in entries}


class RequestGuard:
    """Check HTTP destinations and cap requests within one browser context.

    DNS is checked before Playwright fetches. This is a best-effort local guard,
    not a network sandbox: the HTTP client resolves names independently.
    """

    def __init__(self, max_requests: int = 100):
        self.max_requests = max_requests
        self.count = 0
        self.addresses: dict[str, set[str]] = {}

    async def check(self, url: str, method: str = "GET") -> str | None:
        self.count += 1
        if self.count > self.max_requests:
            return "request limit reached"
        if method not in {"GET", "HEAD"}:
            return "only GET and HEAD requests are allowed"
        try:
            host = validate_url(url)
            if host == "localhost" or host.endswith(".localhost"):
                return "local hostname blocked"
            if host not in self.addresses:
                self.addresses[host] = await asyncio.wait_for(resolve_addresses(host), timeout=3)
            addresses = self.addresses[host]
            if not addresses:
                return "DNS returned no addresses"
            if any(
                not ipaddress.ip_address(address).is_global
                or ipaddress.ip_address(address).is_multicast
                for address in addresses
            ):
                return "non-public IP address blocked"
        except (OSError, ValueError, TimeoutError) as exc:
            return f"destination check failed: {exc}"
        return None
