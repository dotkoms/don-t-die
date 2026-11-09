"""CLI: python3 -m dontdie <command>."""
from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import landing, store
from .sources import SOURCES


def cmd_research(args: argparse.Namespace) -> int:
    """Multi-agent research run for one target. Dry run unless --go."""
    from .agents import research

    return research.run(args.target, go=args.go, model=args.model)


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


def cmd_migrate(args: argparse.Namespace) -> int:
    applied = store.migrate()
    print("migrations applied:", applied if applied else "none (up to date)")
    return 0


def cmd_load(args: argparse.Namespace) -> int:
    stats = store.load()
    print(
        f"loaded {stats['total']} items ({stats['new']} new) — "
        f"{stats['relevant']} relevant, {stats['excluded']} excluded"
    )
    landing.append_fetch_log({"command": "load", "stats": stats})
    return 0


def cmd_integrity(args: argparse.Namespace) -> int:
    """Retraction Watch pass: flag corpus items that have been retracted."""
    from . import integrity

    stats = integrity.refresh()
    print(
        f"integrity: {stats['retraction_records']} retraction records, "
        f"{stats['checked']} corpus items checked, "
        f"{stats['flagged']} flagged"
    )
    landing.append_fetch_log({"command": "integrity", "stats": stats})
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """fetch + load + integrity — the cron entrypoint."""
    fetch_args = argparse.Namespace(
        sources=args.sources, days=args.days, limit=args.limit
    )
    status = cmd_fetch(fetch_args)
    if status != 0:
        return status
    status = cmd_load(args)
    if status != 0:
        return status
    return cmd_integrity(args)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="dontdie", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_fetch = sub.add_parser("fetch", help="fetch from all or selected sources")
    p_load = sub.add_parser("load", help="load the landing zone into Postgres")
    p_integrity = sub.add_parser(
        "integrity",
        help="Retraction Watch pass: flag retracted corpus items",
    )
    p_migrate = sub.add_parser("migrate", help="apply pending migrations")
    p_run = sub.add_parser(
        "run", help="fetch then load then integrity (cron entrypoint)"
    )
    p_research = sub.add_parser(
        "research", help="multi-agent research note for a target (dry run)"
    )
    p_research.add_argument("target", help="research target, e.g. 'BPC-157'")
    p_research.add_argument(
        "--go", action="store_true",
        help="actually run the paid LLM job (explicit, per-job approval)",
    )
    p_research.add_argument(
        "--model", default=None, help="override DD_RESEARCH_MODEL"
    )
    for p in (p_fetch, p_run):
        p.add_argument("--source", dest="sources", action="append", help="repeatable")
        p.add_argument("--days", type=int, default=7, help="trailing window (default 7)")
        p.add_argument("--limit", type=int, default=100, help="per domain query")
    p_fetch.set_defaults(func=cmd_fetch)
    p_load.set_defaults(func=cmd_load)
    p_integrity.set_defaults(func=cmd_integrity)
    p_migrate.set_defaults(func=cmd_migrate)
    p_run.set_defaults(func=cmd_run)
    p_research.set_defaults(func=cmd_research)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
