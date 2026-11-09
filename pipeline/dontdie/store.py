"""Postgres store: migrations + item upserts. The pipeline owns the schema.

Connection comes from DATABASE_URL (no default — no implicit database). The
site connects with a separate read-only role; this module is the write side.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

import psycopg2

from . import config
from .relevance import tag
from .sources import rss

MIGRATIONS_DIR = config.PIPELINE_ROOT / "migrations"

SEED_SOURCES = [
    ("pubmed", "PubMed", "https://pubmed.ncbi.nlm.nih.gov/", 1),
    ("ctgov", "ClinicalTrials.gov", "https://clinicaltrials.gov/", 1),
    # News outlets are tier 2: derived reporting, never primary sources.
    *[(slug, name, url, 2) for slug, name, url, _ua in rss.FEEDS],
]


def connect(dsn: Optional[str] = None):
    """Connect using DATABASE_URL (or an explicit dsn, used by tests)."""
    import os

    dsn = dsn or os.environ.get("DATABASE_URL")
    if not dsn:
        raise SystemExit("DATABASE_URL is not set — refusing to guess a database.")
    return psycopg2.connect(dsn)


def migrate(dsn: Optional[str] = None) -> list:
    """Apply every not-yet-applied migration in pipeline/migrations/, in order."""
    conn = connect(dsn)
    applied = []
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
            )
            cur.execute("SELECT name FROM schema_migrations")
            done = {row[0] for row in cur.fetchall()}
            for path in sorted(Path(MIGRATIONS_DIR).glob("*.sql")):
                if path.name in done:
                    continue
                cur.execute(path.read_text())
                cur.execute(
                    "INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,)
                )
                applied.append(path.name)
    finally:
        conn.close()
    return applied


def _upsert_source(cur, slug: str, name: str, url: str, tier: int) -> None:
    cur.execute(
        "INSERT INTO sources (slug, name, url, tier) VALUES (%s, %s, %s, %s) "
        "ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name, url = EXCLUDED.url",
        (slug, name, url, tier),
    )


def upsert_item(cur, record: Dict[str, Any]) -> bool:
    """Insert or update one item from a landing-zone record (already tagged).

    Returns True if the row was new. Domain query hits go to item_domains;
    relevance is stored but does NOT drop the row — excluded items stay in the
    corpus, out of the public views (they are why the gate is auditable).
    """
    source = record["source"]
    source_id = record["item_id"]
    slug = record.get("slug") or f"{source}-{source_id}"
    raw = {
        k: v
        for k, v in record.items()
        if k
        not in (
            "source",
            "item_id",
            "payload",
            "is_relevant",
            "relevance_terms",
            "relevance_method",
        )
    }
    cur.execute(
        """
        SELECT id FROM items WHERE source = %s AND source_id = %s
        """,
        (source, source_id),
    )
    row = cur.fetchone()

    if row:
        cur.execute(
            """
            UPDATE items
            SET raw = %s, updated_at = now(),
                is_relevant = %s, relevance_terms = %s, relevance_method = %s
            WHERE id = %s
            """,
            (
                json.dumps(raw, default=str),
                record.get("is_relevant", False),
                json.dumps(record.get("relevance_terms", [])),
                record.get("relevance_method", ""),
                row[0],
            ),
        )
        item_id, is_new = row[0], False
    else:
        cur.execute(
            """
            INSERT INTO items
                (source, source_id, slug, url, title, published, raw,
                 is_relevant, relevance_terms, relevance_method)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                source,
                source_id,
                slug,
                record.get("url", ""),
                record.get("title", ""),
                record.get("published") or None,
                json.dumps(raw, default=str),
                record.get("is_relevant", False),
                json.dumps(record.get("relevance_terms", [])),
                record.get("relevance_method", ""),
            ),
        )
        item_id, is_new = cur.fetchone()[0], True

    domain = record.get("domain_query")
    if domain:
        cur.execute(
            "INSERT INTO item_domains (item_id, domain) VALUES (%s, %s) "
            "ON CONFLICT DO NOTHING",
            (item_id, domain),
        )
    return is_new


def iter_landing() -> Iterator[Dict[str, Any]]:
    """Yield every landed item record from the landing zone."""
    if not config.LANDING_DIR.exists():
        return
    for path in sorted(config.LANDING_DIR.glob("*/*.json")):
        yield json.loads(path.read_text())


def load(dsn: Optional[str] = None) -> Dict[str, int]:
    """Load the landing zone into Postgres; returns a summary."""
    conn = connect(dsn)
    stats = {"total": 0, "new": 0, "relevant": 0, "excluded": 0}
    try:
        with conn, conn.cursor() as cur:
            for source in SEED_SOURCES:
                _upsert_source(cur, *source)
            for record in iter_landing():
                tagged = tag(record)
                if upsert_item(cur, tagged):
                    stats["new"] += 1
                stats["total"] += 1
                if tagged["is_relevant"]:
                    stats["relevant"] += 1
                else:
                    stats["excluded"] += 1
    finally:
        conn.close()
    return stats


def save_research_note(note: Dict[str, Any],
                       dsn: Optional[str] = None) -> int:
    """Persist one agent-synthesized research note (idempotent by slug).

    Like extractions, the note is labeled with the model that wrote it and
    never merges with source truth; only verified sources are attached.
    Returns the note id.
    """
    conn = connect(dsn)
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO research_notes (slug, target, summary, model, status)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (slug) DO UPDATE
                    SET summary = EXCLUDED.summary, model = EXCLUDED.model,
                        status = EXCLUDED.status
                RETURNING id
                """,
                (
                    note["slug"], note["target"], note["summary"],
                    note["model"], note.get("status", "draft"),
                ),
            )
            note_id = cur.fetchone()[0]
            for src in note.get("sources", []):
                cur.execute(
                    """
                    INSERT INTO research_note_sources
                        (note_id, kind, title, url, verified)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (note_id, url) DO UPDATE
                        SET kind = EXCLUDED.kind, title = EXCLUDED.title,
                            verified = EXCLUDED.verified
                    """,
                    (note_id, src.get("kind", ""), src.get("title", ""),
                     src["url"], bool(src.get("verified", False))),
                )
    finally:
        conn.close()
    return note_id
