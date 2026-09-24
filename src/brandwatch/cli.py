"""Command line interface for discovery and browser evidence collection."""

import argparse
import asyncio
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from brandwatch.collection import DEMO_URL, CollectionError, CollectionSettings, collect_urls
from brandwatch.config import BrandConfig
from brandwatch.discovery import DiscoveryError, read_seed_file, search_crtsh
from brandwatch.hosts import normalize_hostname
from brandwatch.network import validate_url
from brandwatch.storage import (
    connect,
    list_candidates,
    list_collections,
    save_candidates,
    save_collection,
)


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="brandwatch")
    parser.add_argument("--db", type=Path, default=Path("data/brandwatch.db"))
    commands = parser.add_subparsers(dest="command", required=True)
    discover = commands.add_parser("discover", help="Discover candidate domains")
    discover.add_argument("--config", type=Path, default=Path("config/brand.example.toml"))
    discover.add_argument("--source", choices=("file", "ct"), required=True)
    discover.add_argument("--input", type=Path, help="Seed file, required for --source file")
    commands.add_parser("list", help="List stored candidates")
    collect = commands.add_parser("collect", help="Visit candidates and save rendered evidence")
    selection = collect.add_mutually_exclusive_group()
    selection.add_argument(
        "--url", action="append", help="Exact URL of a stored candidate; repeatable"
    )
    selection.add_argument(
        "--demo", action="store_true", help="Render the local demo without network"
    )
    collect.add_argument(
        "--limit", type=int, default=5, help="Maximum URLs per run, 1-25 (default: 5)"
    )
    collect.add_argument("--output", type=Path, default=Path("data/evidence"))
    collect.add_argument("--timeout-ms", type=int, default=15000, help="Total visit time budget")
    collect.add_argument(
        "--render-wait-ms", type=int, default=1000, help="Wait for JavaScript rendering"
    )
    evidence = commands.add_parser("evidence", help="List the most recent collection results")
    evidence.add_argument("--limit", type=int, default=20)
    return parser


def select_urls(
    connection: sqlite3.Connection, requested: list[str] | None, limit: int
) -> list[str]:
    """Limit visits to candidates already discovered; preserve explicitly supplied URL paths."""
    if not 1 <= limit <= 25:
        raise ValueError("limit must be between 1 and 25")
    known = {host for host, _ in list_candidates(connection)}
    if requested:
        urls = list(dict.fromkeys(requested))
        if len(urls) > limit:
            raise ValueError("Too many URLs; increase --limit (up to 25)")
        for url in urls:
            host = validate_url(url)
            if host not in known or normalize_hostname(url) != host:
                raise ValueError(f"Discover hostname {host} before collecting it")
        return urls
    return [f"https://{host}/" for host in sorted(known)[:limit]]


def run_collection(args) -> int:
    settings = CollectionSettings(timeout_ms=args.timeout_ms, render_wait_ms=args.render_wait_ms)
    if not 1 <= args.limit <= 25:
        raise ValueError("limit must be between 1 and 25")
    with closing(connect(args.db)) as connection:
        if args.demo:
            save_candidates(connection, {validate_url(DEMO_URL)}, "demo")
            urls = [DEMO_URL]
        else:
            urls = select_urls(connection, args.url, args.limit)
        if not urls:
            print("No candidates to collect. Run discover first, or use collect --demo.")
            return 0
        results = asyncio.run(collect_urls(urls, args.output, settings, demo=args.demo))
        for result in results:
            save_collection(connection, result)
            print(f"{result.hostname}\t{result.status}\t{result.evidence_path}")
        return int(any(result.status != "ok" for result in results))


def main(argv: list[str] | None = None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "discover":
            config = BrandConfig.load(args.config)
            if args.source == "file":
                if args.input is None:
                    parser.error("--input is required for --source file")
                hosts = read_seed_file(args.input, config)
            else:
                if args.input is not None:
                    parser.error("--input is only used with --source file")
                hosts = search_crtsh(config)
            with closing(connect(args.db)) as connection:
                count = save_candidates(connection, hosts, args.source)
            print(f"Stored {count} candidate(s) from {args.source}.")
        elif args.command == "collect":
            return run_collection(args)
        elif args.command == "evidence":
            if not 1 <= args.limit <= 100:
                raise ValueError("evidence limit must be between 1 and 100")
            with closing(connect(args.db)) as connection:
                for run_id, host, status, path in list_collections(connection, args.limit):
                    print(f"{run_id}\t{host}\t{status}\t{path}")
        else:
            with closing(connect(args.db)) as connection:
                for host, sources in list_candidates(connection):
                    print(f"{host}\t{sources}")
    except (OSError, ValueError, sqlite3.Error, DiscoveryError, CollectionError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
