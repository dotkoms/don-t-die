"""Weekly digest — 'what changed this week' as one editorial issue per ISO
calendar week (Mon–Sun).

Fully deterministic: no model and no fetches, just a recompute over the
corpus, like the retraction flags. An issue collects every relevant,
un-retracted item whose own source date — publication, trial update, trial
registration, grant start — falls inside the week, groups them into domain
sections and ranks them in the plan's editorial order (decision 5): trial
activity first, then papers, funding, preprints, media echo; within a group
more gate-term matches rank earlier, then newer first.

Two deliberate exclusions:
- Items without any date (the curated snapshot datasets: DrugAge, GenAge,
  CellAge, AnAge) never enter a digest — a re-landed snapshot is not a
  weekly change.
- Weeks before the pipeline's first fetch get no issues. The digest is the
  live stream's editorial unit: it answers "what changed while we watched",
  and backfilling 1977 grant-start weeks would be backfill theater, not news.

Tier-2 news items carry no domain (domain pages are primary-only), so an
issue groups them in a "coverage" section instead of dropping them.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from . import store

# Editorial rank groups (decision 5: human-trial results > papers >
# funding/regulatory > preprints > media echo). "Strong animal results"
# stay merged with papers until extraction (M5) can tell them apart.
CATEGORIES = {
    "trial": 0,
    "paper": 1,
    "grant": 2,
    "preprint": 3,
    "news": 4,
}

_STAT_KEYS = {
    "trial": "trials",
    "paper": "papers",
    "grant": "grants",
    "preprint": "preprints",
    "news": "news",
}

_TRIAL_SOURCES = {"ctgov", "isrctn", "ctis"}
_GRANT_SOURCES = {"reporter", "cordis", "gtr"}


def category(source: str, raw: Dict[str, Any]) -> str:
    """The editorial group an item's source puts it in."""
    if source in _TRIAL_SOURCES:
        return "trial"
    if source in _GRANT_SOURCES:
        return "grant"
    if source == "europemc" and raw.get("preprint"):
        return "preprint"
    if source in ("pubmed", "europemc"):
        return "paper"
    return "news"


def _parse_day(text: Optional[str]) -> Optional[date]:
    """ISO dates, plus the DD/MM/YYYY the EU CTIS API uses."""
    if not text:
        return None
    text = text.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def editorial_date(published: Any, raw: Dict[str, Any]) -> Optional[date]:
    """The item's own source date: publication first, then a trial's
    update / registration / decision date. None means the item has no date
    at all (curated snapshot rows) and never enters a digest."""
    if published:
        return published if isinstance(published, date) else _parse_day(str(published))
    for key in ("last_update", "registration_date", "decision_date"):
        day = _parse_day(raw.get(key))
        if day:
            return day
    return None


def week_slug(day: date) -> str:
    iso = day.isocalendar()
    return f"{iso[0]}-w{iso[1]:02d}"


def rank_key(record: Dict[str, Any]) -> Tuple:
    """Category first (editorial order), then more gate-term matches
    earlier, then newer first, then slug as the stable tiebreak."""
    return (
        CATEGORIES[record["category"]],
        -len(record["terms"]),
        -record["day"].toordinal(),
        record["slug"],
    )


def build(dsn: Optional[str] = None) -> Dict[str, Any]:
    """Recompute every weekly issue from first fetch to the current week.

    Idempotent: issue rows upsert by slug, their items are deleted and
    re-inserted, and issues whose weeks no longer have items are removed.
    """
    conn = store.connect(dsn)
    issues: Dict[date, List[Dict[str, Any]]] = {}
    today = date.today()
    try:
        with conn, conn.cursor() as cur:
            # The digest exists from the pipeline's first fetch onward.
            cur.execute("SELECT min(fetched_at)::date FROM items")
            first_day = cur.fetchone()[0]
            if first_day is None:
                return {"issues": 0, "items": 0}
            first_week = first_day - timedelta(days=first_day.weekday())
            current_week = today - timedelta(days=today.weekday())

            cur.execute(
                """
                SELECT DISTINCT ON (i.id)
                       i.id, i.source, i.slug, i.published, i.raw,
                       i.relevance_terms, d.domain
                FROM items i
                LEFT JOIN item_domains d ON d.item_id = i.id
                WHERE i.is_relevant AND NOT i.is_retracted
                ORDER BY i.id, d.is_primary DESC, d.domain
                """
            )
            for item_id, source, slug, published, raw, terms, domain in cur:
                day = editorial_date(published, raw or {})
                if day is None:
                    continue
                week_start = day - timedelta(days=day.weekday())
                if week_start < first_week or week_start > current_week:
                    continue
                issues.setdefault(week_start, []).append({
                    "item_id": item_id,
                    "slug": slug,
                    "category": category(source, raw or {}),
                    "terms": terms or [],
                    "day": day,
                    # Tier-2 news carries no domain (domain pages are
                    # primary-only), so the issue gives it its own
                    # "coverage" section instead.
                    "domain": domain or "coverage",
                })

            total = 0
            for week_start, records in sorted(issues.items()):
                records.sort(key=rank_key)
                week_end = week_start + timedelta(days=6)
                stats: Dict[str, Any] = {
                    "items": len(records),
                    "sections": {},
                }
                for key in _STAT_KEYS.values():
                    stats[key] = 0
                for rec in records:
                    stats[_STAT_KEYS[rec["category"]]] += 1
                    stats["sections"][rec["domain"]] = (
                        stats["sections"].get(rec["domain"], 0) + 1
                    )

                cur.execute(
                    """
                    INSERT INTO digests (slug, week_start, week_end, stats)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (slug) DO UPDATE
                        SET week_start = EXCLUDED.week_start,
                            week_end = EXCLUDED.week_end,
                            built_at = now(),
                            stats = EXCLUDED.stats
                    RETURNING id
                    """,
                    (week_slug(week_start), week_start, week_end,
                     json.dumps(stats)),
                )
                digest_id = cur.fetchone()[0]
                cur.execute(
                    "DELETE FROM digest_items WHERE digest_id = %s",
                    (digest_id,),
                )
                cur.executemany(
                    "INSERT INTO digest_items (digest_id, item_id, rank, section)"
                    " VALUES (%s, %s, %s, %s)",
                    [(digest_id, r["item_id"], n, r["domain"])
                     for n, r in enumerate(records, start=1)],
                )
                total += len(records)

            # Issues whose weeks no longer have items (retractions, gate
            # changes) must not linger.
            cur.execute(
                "DELETE FROM digests WHERE week_start NOT IN %s",
                (tuple(issues.keys()),),
            )
    finally:
        conn.close()

    if not issues:
        return {"issues": 0, "items": 0}
    latest = max(issues)
    return {
        "issues": len(issues),
        "items": total,
        "latest_slug": week_slug(latest),
        "latest_items": len(issues[latest]),
    }
