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


def cmd_digest(args: argparse.Namespace) -> int:
    """Weekly digest: recompute every issue from the corpus (no LLM)."""
    from . import digest

    stats = digest.build()
    print(
        f"digest: {stats['issues']} issues, {stats['items']} ranked items "
        f"(latest {stats.get('latest_slug')}: "
        f"{stats.get('latest_items')} items)"
    )
    landing.append_fetch_log({"command": "digest", "stats": stats})
    return 0


def cmd_entities(args: argparse.Namespace) -> int:
    """Entity pages: rebuild compounds, orgs and trials from the corpus."""
    from . import entities

    stats = entities.build()
    print(
        f"entities: {stats['compounds']} compounds, "
        f"{stats['orgs']} organizations, {stats['trials']} trials — "
        f"{stats['links']} item links"
    )
    landing.append_fetch_log({"command": "entities", "stats": stats})
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    """LLM extraction pass. Dry run unless --go; never part of `run`."""
    from . import extract

    if args.collect is not None:
        stats = extract.collect(args.collect or None)
        if stats.get("pending"):
            print(
                f"batch {stats['batch_id']}: still {stats['status']} — "
                "results are not ready; re-run --collect later"
            )
            return 0
        print(
            f"collect {stats['batch_id']}: {stats['stored']} items stored, "
            f"{stats['failed']} failed"
        )
        landing.append_fetch_log({"command": "extract-collect", "stats": stats})
        return 0

    model = args.model or extract.MODEL
    stats = extract.run(
        go=args.go, model=model, limit=args.limit, batch=args.batch,
    )
    if not stats["go"]:
        print(f"extract dry run — model {stats['model']}")
        print(
            f"{stats['pending']} pending items "
            f"({stats['already']} already extracted with this model)"
        )
        print(
            f"~{stats['input_tokens']:,} input + "
            f"~{stats['output_tokens']:,} output tokens "
            f"(list-price estimate): "
            f"${stats['realtime']:.4f} realtime, "
            f"${stats['batch']:.4f} via Batch API"
        )
        if stats["sample_prompt"]:
            sample = stats["sample_prompt"]
            print("\nsample prompt (first item):")
            print(f"  {sample[:300]}{'…' if len(sample) > 300 else ''}")
        print(
            "\nre-run with --go to spend it (realtime), or --go --batch "
            "for the half-price Batch API backfill"
        )
        return 0
    if stats["batch"]:
        print(
            f"batch submitted: {stats['items']} items, "
            f"batch id(s) {', '.join(stats['batch_ids'])} "
            "(recorded in state/extraction_batch.json)"
        )
        print("results arrive in minutes to hours; collect with --collect")
        landing.append_fetch_log(
            {"command": "extract-batch", "stats": stats}
        )
        return 0
    print(
        f"extract: {stats['extracted']} extracted, {stats['failed']} failed "
        f"({stats['fields']} fields written)"
    )
    landing.append_fetch_log({"command": "extract", "stats": stats})
    return 1 if stats["failed"] else 0


def cmd_run(args: argparse.Namespace) -> int:
    """fetch + load + integrity + digest + entities — the cron entrypoint."""
    fetch_args = argparse.Namespace(
        sources=args.sources, days=args.days, limit=args.limit
    )
    status = cmd_fetch(fetch_args)
    if status != 0:
        return status
    for step in (cmd_load, cmd_integrity, cmd_digest, cmd_entities):
        status = step(args)
        if status != 0:
            return status
    return 0


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
    p_digest = sub.add_parser(
        "digest",
        help="weekly digest: recompute every issue from the corpus",
    )
    p_entities = sub.add_parser(
        "entities",
        help="rebuild entity pages: compounds, organizations, trials",
    )
    p_run = sub.add_parser(
        "run",
        help="fetch, load, integrity, digest, entities (cron entrypoint)",
    )
    p_research = sub.add_parser(
        "research", help="multi-agent research note for a target (dry run)"
    )
    p_extract = sub.add_parser(
        "extract",
        help="LLM extraction pass: summarize + tag relevant items "
             "(dry run by default)",
    )
    p_extract.add_argument(
        "--go", action="store_true",
        help="actually run the paid LLM job (explicit, per-job approval)",
    )
    p_extract.add_argument(
        "--batch", action="store_true",
        help="with --go: submit via the Batch API (half price) instead of "
             "sequential realtime calls",
    )
    p_extract.add_argument(
        "--collect", nargs="?", const="",
        help="download the results of a submitted batch (free; bare = the "
             "recorded batch, or pass a batch id)",
    )
    p_extract.add_argument(
        "--limit", type=int, default=None,
        help="extract at most N items this run",
    )
    p_extract.add_argument(
        "--model", default=None, help="override DD_EXTRACT_MODEL",
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
    p_digest.set_defaults(func=cmd_digest)
    p_entities.set_defaults(func=cmd_entities)
    p_run.set_defaults(func=cmd_run)
    p_research.set_defaults(func=cmd_research)
    p_extract.set_defaults(func=cmd_extract)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
