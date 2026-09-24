"""Command line interface for discovery, enrichment and browser evidence collection."""

import argparse
import asyncio
import json
import sqlite3
import sys
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from brandwatch.analysis import analyze_evidence_file
from brandwatch.collection import DEMO_URL, CollectionError, CollectionSettings, collect_urls
from brandwatch.config import BrandConfig
from brandwatch.dashboard import render_dashboard_file
from brandwatch.discovery import (
    MAX_CT_QUERIES,
    DiscoveryError,
    read_seed_findings,
    search_crtsh_findings,
)
from brandwatch.enrichment import enrich_hostname
from brandwatch.hosts import normalize_hostname
from brandwatch.network import validate_url
from brandwatch.reporting import build_cases, build_report, write_report
from brandwatch.storage import (
    connect,
    list_actions,
    list_analyses,
    list_candidates,
    list_collection_records,
    list_collections,
    list_discovery_matches,
    list_enrichments,
    list_latest_analyses,
    save_action,
    save_analysis,
    save_candidates,
    save_collection,
    save_enrichment,
    save_findings,
)
from brandwatch.typos import generate_variants


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="brandwatch")
    parser.add_argument("--db", type=Path, default=Path("data/brandwatch.db"))
    commands = parser.add_subparsers(dest="command", required=True)

    discover = commands.add_parser("discover", help="Discover candidate domains")
    discover.add_argument("--config", type=Path, default=Path("config/brand.example.toml"))
    discover.add_argument("--source", choices=("file", "ct"), required=True)
    discover.add_argument("--input", type=Path, help="Seed file, required for --source file")
    discover.add_argument(
        "--ct-limit",
        type=int,
        default=MAX_CT_QUERIES,
        help=f"Maximum crt.sh queries, 1-{MAX_CT_QUERIES} (default: {MAX_CT_QUERIES})",
    )

    variants = commands.add_parser("variants", help="Preview generated typo hypotheses offline")
    variants.add_argument("--config", type=Path, default=Path("config/brand.example.toml"))
    variants.add_argument("--limit", type=int, default=20)

    commands.add_parser("list", help="List stored candidates")
    matches = commands.add_parser("matches", help="List discovery term provenance")
    matches.add_argument("--limit", type=int, default=100)

    enrich = commands.add_parser("enrich", help="Attach current DNS and RDAP context")
    enrich.add_argument("--host", action="append", help="Stored candidate hostname; repeatable")
    enrich.add_argument("--limit", type=int, default=5, help="Maximum candidates per run, 1-25")
    enrich.add_argument("--timeout", type=int, default=8, help="RDAP timeout in seconds, 1-30")

    context = commands.add_parser("context", help="List recent DNS/RDAP enrichment results")
    context.add_argument("--limit", type=int, default=20)

    analyze = commands.add_parser("analyze", help="Score saved browser evidence")
    analyze.add_argument("--config", type=Path, default=Path("config/brand.example.toml"))
    analyze.add_argument("--host", action="append", help="Stored hostname; repeatable")
    analyze.add_argument("--limit", type=int, default=25, help="Maximum evidence records, 1-100")
    analyze.add_argument(
        "--ocr", action="store_true", help="Use local Tesseract when DOM evidence is sparse"
    )
    analysis_list = commands.add_parser("analyses", help="List saved analysis results")
    analysis_list.add_argument("--limit", type=int, default=20)

    report = commands.add_parser("report", help="Write a local case report")
    report.add_argument("--config", type=Path, default=Path("config/brand.example.toml"))
    report.add_argument("--output", type=Path, default=Path("data/report.json"))
    report.add_argument(
        "--format", choices=("json", "csv"), help="Output format (default: extension)"
    )
    report.add_argument("--limit", type=int, default=100, help="Maximum latest analyses, 1-1000")
    report.add_argument(
        "--decision",
        choices=("all", "review", "no_action"),
        default="all",
        help="Include all cases or one local decision category",
    )
    actions = commands.add_parser("actions", help="List local report decisions")
    actions.add_argument("--limit", type=int, default=100)

    dashboard = commands.add_parser("dashboard", help="Create a local HTML case dashboard")
    dashboard.add_argument("--input", type=Path, default=Path("data/report.json"))
    dashboard.add_argument("--output", type=Path, default=Path("data/dashboard.html"))

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


def select_hosts(
    connection: sqlite3.Connection, requested: list[str] | None, limit: int
) -> list[str]:
    if not 1 <= limit <= 25:
        raise ValueError("limit must be between 1 and 25")
    known = {host for host, _ in list_candidates(connection)}
    if requested:
        hosts = []
        for host in dict.fromkeys(requested):
            normalized = normalize_hostname(host)
            if normalized is None or normalized not in known:
                raise ValueError(f"Discover hostname {host} before enriching it")
            if normalized not in hosts:
                hosts.append(normalized)
        if len(hosts) > limit:
            raise ValueError("Too many hosts; increase --limit (up to 25)")
        return hosts
    return sorted(known)[:limit]


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


def run_enrichment(args) -> int:
    if not 1 <= args.timeout <= 30:
        raise ValueError("timeout must be between 1 and 30 seconds")
    with closing(connect(args.db)) as connection:
        hosts = select_hosts(connection, args.host, args.limit)
        if not hosts:
            print("No candidates to enrich. Run discover first.")
            return 0
        failed = False
        for host in hosts:
            result = enrich_hostname(host, timeout=args.timeout)
            save_enrichment(connection, result)
            addresses = len(result.dns.get("ipv4", [])) + len(result.dns.get("ipv6", []))
            print(f"{host}\t{result.status}\taddresses={addresses}\trdap={bool(result.rdap)}")
            failed |= result.status == "error"
        return int(failed)


def run_analysis(args) -> int:
    if not 1 <= args.limit <= 100:
        raise ValueError("analysis limit must be between 1 and 100")
    config = BrandConfig.load(args.config)
    with closing(connect(args.db)) as connection:
        records = list_collection_records(connection, args.limit)
        if args.host:
            requested = set(args.host)
            records = [record for record in records if record[1] in requested]
        if not records:
            print("No collection evidence to analyze. Run collect first.")
            return 0
        matches = list_discovery_matches(connection, 1000)
        enrichment_by_host = {}
        for _, host, _, _, payload in list_enrichments(connection, 1000):
            if host not in enrichment_by_host:
                try:
                    enrichment_by_host[host] = json.loads(payload)
                except json.JSONDecodeError:
                    continue
        for collection_id, host, status, evidence_path in records:
            result = analyze_evidence_file(
                evidence_path,
                config,
                discovery_matches=[row for row in matches if row[0] == host],
                enrichment=enrichment_by_host.get(host),
                use_ocr=args.ocr,
            )
            result.collection_id = collection_id
            result.hostname = result.hostname or host
            if status != "ok" and result.label != "insufficient_evidence":
                result.label = "insufficient_evidence"
            save_analysis(connection, result)
            print(
                f"{host}\t{result.score}\t{result.label}\t"
                f"factors={json.dumps(result.factors, sort_keys=True)}"
            )
    return 0


def run_report(args) -> int:
    if not 1 <= args.limit <= 1000:
        raise ValueError("report limit must be between 1 and 1000")
    config = BrandConfig.load(args.config)
    output_format = args.format or args.output.suffix.removeprefix(".") or "json"
    with closing(connect(args.db)) as connection:
        analyses = list_latest_analyses(connection, args.limit)
        collections = {
            row[0]: (row[2], row[3]) for row in list_collection_records(connection, 1000)
        }
        matches = list_discovery_matches(connection, 5000)
        enrichments = {}
        for _, host, collected_at, status, payload in list_enrichments(connection, 5000):
            if host not in enrichments:
                try:
                    enrichments[host] = (status, collected_at, json.loads(payload))
                except json.JSONDecodeError:
                    continue
        cases = build_cases(analyses, collections, matches, enrichments, args.decision)
        document = build_report(config, cases)
        write_report(document, args.output, output_format)
        created_at = datetime.now(UTC).isoformat()
        for case in cases:
            save_action(
                connection,
                uuid4().hex,
                case["analysis_id"],
                case["hostname"],
                created_at,
                case["recommended_decision"],
                str(args.output),
            )
    print(f"Wrote {len(cases)} case(s) to {args.output} ({output_format}).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "discover":
            config = BrandConfig.load(args.config)
            if args.source == "file":
                if args.input is None:
                    parser.error("--input is required for --source file")
                if args.ct_limit != MAX_CT_QUERIES:
                    parser.error("--ct-limit is only used with --source ct")
                findings = read_seed_findings(args.input, config)
            else:
                if args.input is not None:
                    parser.error("--input is only used with --source file")
                findings = search_crtsh_findings(config, max_queries=args.ct_limit)
            with closing(connect(args.db)) as connection:
                count = save_findings(connection, findings, args.source)
            print(f"Stored {count} candidate(s) from {args.source}.")
        elif args.command == "variants":
            config = BrandConfig.load(args.config)
            for variant in generate_variants(config, limit=args.limit):
                print(f"{variant.value}\t{variant.base}\t{variant.rule}")
        elif args.command == "matches":
            if not 1 <= args.limit <= 1000:
                raise ValueError("matches limit must be between 1 and 1000")
            with closing(connect(args.db)) as connection:
                for row in list_discovery_matches(connection, args.limit):
                    print("\t".join(row))
        elif args.command == "enrich":
            return run_enrichment(args)
        elif args.command == "context":
            if not 1 <= args.limit <= 100:
                raise ValueError("context limit must be between 1 and 100")
            with closing(connect(args.db)) as connection:
                for run_id, host, collected_at, status, payload in list_enrichments(
                    connection, args.limit
                ):
                    data = json.loads(payload)
                    addresses = len(data["dns"].get("ipv4", [])) + len(
                        data["dns"].get("ipv6", [])
                    )
                    print(f"{run_id}\t{host}\t{status}\t{collected_at}\taddresses={addresses}")
        elif args.command == "analyze":
            return run_analysis(args)
        elif args.command == "analyses":
            if not 1 <= args.limit <= 100:
                raise ValueError("analysis limit must be between 1 and 100")
            with closing(connect(args.db)) as connection:
                for row in list_analyses(connection, args.limit):
                    run_id, collection_id, host, analyzed_at, score, label, version, payload = row
                    print(f"{run_id}\t{collection_id}\t{host}\t{analyzed_at}\t{score}\t{label}\t{version}")
        elif args.command == "report":
            return run_report(args)
        elif args.command == "actions":
            if not 1 <= args.limit <= 1000:
                raise ValueError("action limit must be between 1 and 1000")
            with closing(connect(args.db)) as connection:
                for row in list_actions(connection, args.limit):
                    print("\t".join(row))
        elif args.command == "dashboard":
            render_dashboard_file(args.input, args.output)
            print(f"Wrote local dashboard to {args.output}.")
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
