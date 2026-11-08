import json
import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="needs DATABASE_URL"
)

from dontdie import store


@pytest.fixture()
def dsn():
    return os.environ["DATABASE_URL"]


@pytest.fixture()
def migrated(dsn):
    applied = store.migrate(dsn)
    return applied


def _clean(dsn):
    conn = store.connect(dsn)
    try:
        with conn, conn.cursor() as cur:
            cur.execute("DELETE FROM item_domains")
            cur.execute("DELETE FROM extractions")
            cur.execute("DELETE FROM items")
        # restore sources seeds so later runs re-seed idempotently
    finally:
        conn.close()


def test_migrate_idempotent(dsn):
    first = store.migrate(dsn)
    second = store.migrate(dsn)
    assert second == []
    assert set(first) <= {"0001_init.sql", "0002_relevance.sql"}


def test_load_upserts_and_dedupes(dsn, migrated, landing_dir):
    _clean(dsn)
    record = {
        "source": "pubmed",
        "item_id": "99990001",
        "title": "Rapamycin and mouse lifespan",
        "url": "https://pubmed.ncbi.nlm.nih.gov/99990001/",
        "published": "2026-10-01",
        "abstract": "Rapamycin extends lifespan in aged mice.",
        "domain_query": "geroscience",
        "payload": {"efetch_xml": "<x/>"},
    }
    landing_dir.joinpath("pubmed").mkdir(parents=True, exist_ok=True)
    landing_dir.joinpath("pubmed/99990001.json").write_text(json.dumps(record))

    stats = store.load(dsn)
    assert stats["total"] == 1 and stats["new"] == 1 and stats["relevant"] == 1

    # Re-load the same landing record: no new row, same item.
    stats2 = store.load(dsn)
    assert stats2["new"] == 0 and stats2["total"] == 1

    conn = store.connect(dsn)
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "SELECT source, source_id, slug, title, is_relevant, "
                "relevance_method FROM items"
            )
            rows = cur.fetchall()
            assert len(rows) == 1
            assert rows[0] == (
                "pubmed",
                "99990001",
                "pubmed-99990001",
                "Rapamycin and mouse lifespan",
                True,
                "keyword-v1",
            )
            cur.execute(
                "SELECT domain FROM item_domains "
                "JOIN items ON items.id = item_domains.item_id"
            )
            assert cur.fetchall() == [("geroscience",)]
    finally:
        conn.close()


def test_load_keeps_excluded_items(dsn, migrated, landing_dir):
    _clean(dsn)
    record = {
        "source": "pubmed",
        "item_id": "99990002",
        "title": "Aging of dental composites",
        "url": "https://pubmed.ncbi.nlm.nih.gov/99990002/",
        "abstract": "Material testing.",
        "payload": {},
    }
    landing_dir.joinpath("pubmed").mkdir(parents=True, exist_ok=True)
    landing_dir.joinpath("pubmed/99990002.json").write_text(json.dumps(record))

    stats = store.load(dsn)
    assert stats["excluded"] == 1 and stats["relevant"] == 0

    conn = store.connect(dsn)
    try:
        with conn, conn.cursor() as cur:
            cur.execute("SELECT is_relevant FROM items WHERE source_id = '99990002'")
            assert cur.fetchone()[0] is False
    finally:
        conn.close()
