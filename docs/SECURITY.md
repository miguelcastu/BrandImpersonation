# Security and safe operation

BrandWatch opens untrusted public pages, so collection is treated as a contained research task. It is a small lab, not a production SSRF boundary.

## Built-in protections

- URLs are limited to HTTP/HTTPS, ports 80/443, no credentials, no whitespace and no control characters.
- Every browser request is restricted to GET/HEAD, has a request and response-size limit, and is checked against current DNS results.
- Loopback, private, link-local, reserved, multicast, unspecified, `.localhost`, `.local`, `.internal`, metadata and Docker hostnames are blocked.
- All addresses returned for a hostname must be public; one private answer blocks the hostname.
- Redirects are fetched with `max_redirects=0`, validated as a new navigation and capped at five hops.
- Playwright uses a fresh non-persistent context, Chromium's sandbox, disabled service workers, no permissions, no downloads, blocked WebSockets and no form submission.
- The offline demo fulfills one bundled document and blocks every network request.

The DNS check is deliberately refreshed for each request. Browser DNS resolution is still performed by Chromium independently, so this guard is best effort and cannot eliminate a DNS-rebinding race by itself.

## Recommended isolation for real testing

Run collection in a disposable VM or an unprivileged container with Chromium's sandbox enabled and a separate network egress policy. Allow outbound TCP 80/443 only through a filtering proxy or firewall, deny RFC1918/link-local/multicast ranges and cloud metadata services, and keep the results directory separate from host secrets. Do not mount home directories, SSH keys, browser profiles, cloud credentials or Docker sockets into the collector.

For the offline demo, use `collect --demo`; it does not require network access. Do not run the collector with administrator/root privileges. A production deployment should add OS-level egress enforcement because application-level DNS checks cannot guarantee destination pinning.
