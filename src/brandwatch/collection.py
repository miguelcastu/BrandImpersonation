"""Bounded Playwright visits that save rendered evidence rather than raw HTML."""

import asyncio
import json
from contextlib import suppress
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from urllib.parse import urljoin
from uuid import uuid4

from brandwatch.network import RequestGuard, validate_url

DEMO_URL = "https://microsoft-login.example/demo"


class CollectionError(Exception):
    """Collection cannot start (for example, the browser is not installed)."""


@dataclass(frozen=True)
class CollectionSettings:
    timeout_ms: int = 15000
    render_wait_ms: int = 1000
    max_requests: int = 100

    def __post_init__(self):
        if not 1000 <= self.timeout_ms <= 60000:
            raise ValueError("timeout must be between 1000 and 60000 milliseconds")
        if not 0 <= self.render_wait_ms <= 5000:
            raise ValueError("render wait must be between 0 and 5000 milliseconds")
        if self.render_wait_ms >= self.timeout_ms:
            raise ValueError("render wait must be smaller than the visit timeout")
        if not 1 <= self.max_requests <= 200:
            raise ValueError("request limit must be between 1 and 200")


@dataclass
class CollectionResult:
    id: str
    hostname: str
    requested_url: str
    started_at: str
    is_demo: bool = False
    completed_at: str = ""
    status: str = "error"
    final_url: str = ""
    http_status: int | None = None
    error: str | None = None
    dom: dict = field(default_factory=dict)
    blocked_requests: list[dict] = field(default_factory=list)
    request_errors: list[dict] = field(default_factory=list)
    redirects: list[str] = field(default_factory=list)
    screenshot_path: str | None = None
    evidence_path: str = ""
    settings: dict = field(default_factory=dict)


async def collect_page(
    browser, url: str, output: Path, settings: CollectionSettings, *, demo: bool = False
) -> CollectionResult:
    """Return evidence, including failed visits, using a fresh browser context."""
    from playwright.async_api import Error as BrowserError
    from playwright.async_api import TimeoutError as BrowserTimeoutError

    result = CollectionResult(
        id=uuid4().hex,
        hostname=validate_url(url),
        requested_url=url,
        started_at=datetime.now(UTC).isoformat(),
        is_demo=demo,
        settings=asdict(settings),
    )
    directory = output.resolve() / result.id
    directory.mkdir(parents=True)
    result.evidence_path = str(directory / "evidence.json")
    guard = RequestGuard(settings.max_requests)
    context = None
    page = None
    blocked_navigation = None
    pending_redirect = None

    def record_block(request_url, reason):
        if len(result.blocked_requests) < 20:
            result.blocked_requests.append({"url": request_url[:2048], "reason": reason})

    async def route_request(route):
        nonlocal blocked_navigation, pending_redirect
        request = route.request
        is_main = request.is_navigation_request() and request.frame == page.main_frame
        if demo:
            # Demo documents are fulfilled locally; every other request is aborted.
            if request.url == DEMO_URL and request.method == "GET":
                await route.fulfill(
                    status=200,
                    content_type="text/html",
                    body=files("brandwatch").joinpath("demo.html").read_text(encoding="utf-8"),
                )
                return
            reason = "demo blocks all network traffic"
        elif request.resource_type == "media":
            reason = "media downloads are disabled"
        else:
            reason = await guard.check(request.url, request.method)
        if reason:
            record_block(request.url, reason)
            if is_main:
                blocked_navigation = reason
            await route.abort("blockedbyclient")
            return
        # Chromium can follow HTTP redirects without invoking the route again.
        # Fetch one response only, then navigate top-level redirects explicitly.
        upstream = None
        try:
            upstream = await route.fetch(max_redirects=0, timeout=settings.timeout_ms)
            headers = upstream.headers
            if 300 <= upstream.status < 400 and "location" in headers:
                destination = urljoin(request.url, headers["location"])
                if is_main:
                    pending_redirect = destination
                    blocked_navigation = "HTTP redirect requires a new checked navigation"
                    # Complete the intermediate document so Chrome does not race its
                    # error-page navigation against our next checked navigation.
                    await route.fulfill(status=200, content_type="text/html", body="")
                else:
                    record_block(destination, "subresource HTTP redirects are disabled")
                    await route.abort("blockedbyclient")
                return
            body = await upstream.body()
            if len(body) > 8_000_000:
                record_block(request.url, "response exceeds 8 MB")
                if is_main:
                    blocked_navigation = "response exceeds 8 MB"
                await route.abort("blockedbyclient")
                return
            if is_main:
                result.http_status = upstream.status
            await route.fulfill(
                status=upstream.status,
                body=body,
                headers={
                    key: value
                    for key, value in headers.items()
                    if key.lower()
                    not in {"content-encoding", "content-length", "transfer-encoding"}
                },
            )
        except BrowserError as exc:
            if len(result.request_errors) < 20:
                result.request_errors.append({"url": request.url[:2048], "error": str(exc)[:500]})
            with suppress(BrowserError):
                await route.abort("failed")
        finally:
            if upstream is not None:
                with suppress(BrowserError):
                    await upstream.dispose()

    async def block_websocket(websocket):
        record_block(websocket.url, "WebSockets are disabled")
        await websocket.close()

    try:
        async with asyncio.timeout(settings.timeout_ms / 1000):
            context = await browser.new_context(
                viewport={"width": 1280, "height": 720},
                service_workers="block",
                accept_downloads=False,
                permissions=[],
            )
            context.set_default_timeout(settings.timeout_ms)
            await context.route("**/*", route_request)
            await context.route_web_socket("**/*", block_websocket)
            page = await context.new_page()
            page.on("popup", lambda popup: asyncio.create_task(popup.close()))
            target = url
            while True:
                validate_url(target)
                pending_redirect = None
                blocked_navigation = None
                response = await page.goto(target, wait_until="domcontentloaded")
                if pending_redirect is None:
                    result.http_status = response.status if response else None
                    break
                if len(result.redirects) >= 5:
                    raise ValueError("HTTP redirect limit reached")
                target = pending_redirect
                result.redirects.append(target)
            await page.wait_for_timeout(settings.render_wait_ms)
            result.dom = await page.evaluate(
                files("brandwatch").joinpath("dom.js").read_text(encoding="utf-8")
            )
            screenshot = directory / "screenshot.png"
            await page.screenshot(path=str(screenshot), full_page=False, animations="disabled")
            result.screenshot_path = str(screenshot)
            if blocked_navigation:
                result.status, result.error = "blocked", blocked_navigation
            else:
                result.status = "http_error" if (result.http_status or 0) >= 400 else "ok"
    except (TimeoutError, BrowserTimeoutError):
        result.status, result.error = "timeout", "visit exceeded the configured time limit"
    except ValueError as exc:
        result.status, result.error = "blocked", str(exc)
    except BrowserError as exc:
        result.status = "blocked" if blocked_navigation else "error"
        result.error = blocked_navigation or str(exc)[:2000]
    finally:
        if page is not None:
            result.final_url = page.url
        if context is not None:
            with suppress(BrowserError, TimeoutError):
                await asyncio.wait_for(context.close(), timeout=5)
    result.completed_at = datetime.now(UTC).isoformat()
    Path(result.evidence_path).write_text(
        json.dumps(asdict(result), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return result


async def collect_urls(
    urls: list[str], output: Path, settings: CollectionSettings, *, demo: bool = False
) -> list[CollectionResult]:
    """Visit at most 25 URLs, sequentially, with no crawl of discovered links."""
    if not 1 <= len(urls) <= 25:
        raise ValueError("Select between 1 and 25 URLs")
    if demo and urls != [DEMO_URL]:
        raise ValueError("Demo collection only supports the built-in fixture URL")
    try:
        from playwright.async_api import Error as BrowserError
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise CollectionError(
            "Install collection with: uv sync --extra browser --extra dev; "
            "then uv run playwright install chromium"
        ) from exc
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                headless=True,
                chromium_sandbox=True,
                args=["--force-webrtc-ip-handling-policy=disable_non_proxied_udp"],
            )
            try:
                return [
                    await collect_page(browser, url, output, settings, demo=demo) for url in urls
                ]
            finally:
                await browser.close()
    except BrowserError as exc:
        raise CollectionError(
            f"Chromium could not run. Try 'uv run playwright install chromium'. Details: {exc}"
        ) from exc
