"""Command line interface for the discovery sprint."""

import argparse
import sys
from contextlib import closing
from pathlib import Path

from brandwatch.config import BrandConfig
from brandwatch.discovery import DiscoveryError, read_seed_file, search_crtsh
from brandwatch.storage import connect, list_candidates, save_candidates


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="brandwatch")
    parser.add_argument("--db", type=Path, default=Path("data/brandwatch.db"))
    commands = parser.add_subparsers(dest="command", required=True)
    discover = commands.add_parser("discover", help="Discover candidate domains")
    discover.add_argument("--config", type=Path, default=Path("config/brand.example.toml"))
    discover.add_argument("--source", choices=("file", "ct"), required=True)
    discover.add_argument("--input", type=Path, help="Seed file, required for --source file")
    commands.add_parser("list", help="List stored candidates")
    return parser


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
        else:
            with closing(connect(args.db)) as connection:
                for host, sources in list_candidates(connection):
                    print(f"{host}\t{sources}")
    except (OSError, ValueError, DiscoveryError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
