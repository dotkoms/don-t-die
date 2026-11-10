import json
import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="needs DATABASE_URL"
)

from dontdie import store

TEST_DB = "dontdie_test"


@pytest.fixture(scope="session")
def dsn():
    """A throwaway database — never the one DATABASE_URL points at.

    These tests DELETE all rows from the items table; pointed at a real
    corpus they would wipe it. So the suite clones DATABASE_URL into a
    scratch database, runs everything there, and drops it afterwards.
    """
    base = os.environ["DATABASE_URL"]
    admin = store.connect(base)
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS {TEST_DB}")
            cur.execute(f"CREATE DATABASE {TEST_DB}")
    finally:
        admin.close()
    yield base.rsplit("/", 1)[0] + f"/{TEST_DB}"
    cleanup = store.connect(base)
    cleanup.autocommit = True
    try:
        with cleanup.cursor() as cur:
            cur.execute(f"DROP DATABASE {TEST_DB}")
    finally:
        cleanup.close()


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
    assert set(first) <= {
        "0001_init.sql", "0002_relevance.sql", "0003_research_notes.sql",
        "0004_integrity.sql", "0005_digest.sql", "0006_entities.sql",
    }


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
                "keyword-v1.2",
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
