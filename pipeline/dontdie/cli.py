"""CLI: python3 -m dontdie <command>."""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from . import landing
from .sources import SOURCES


def cmd_fetch(args: argparse.Namespace) -> int:
    names: List[str] = args.sources or list(SOURCES)
    unknown = [s for s in names if s not in SOURCES]
    if unknown:
        print(f"unknown source(s): {', '.join(unknown)}", file=sys.stderr)
        return 2

    runs = {}
    for name in names:
        summary = SOURCES[name](days=args.days, limit=args.limit)
        runs[name] = summary
        print(
            f"{name}: {summary['total']} items ({summary['new']} new); "
            f"errors: {len(summary.get('errors', []))}"
        )
        for error in summary.get("errors", []):
            print(f"  - {error}", file=sys.stderr)

    landing.append_fetch_log({"command": "fetch", "runs": runs})
    return 0 if all(not r.get("errors") for r in runs.values()) else 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="dontdie", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_fetch = sub.add_parser("fetch", help="fetch from all or selected sources")
    p_fetch.add_argument("--source", dest="sources", action="append", help="repeatable")
    p_fetch.add_argument("--days", type=int, default=7, help="trailing window (default 7)")
    p_fetch.add_argument("--limit", type=int, default=100, help="per domain query")
    p_fetch.set_defaults(func=cmd_fetch)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
