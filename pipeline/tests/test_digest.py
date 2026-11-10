"""Weekly digest (M3): editorial dating, ranking, and the store round-trip."""

import json
import os
from datetime import date

import pytest

from dontdie import digest


# --- pure functions -----------------------------------------------------------

def test_category_groups():
    assert digest.category("ctgov", {}) == "trial"
    assert digest.category("isrctn", {}) == "trial"
    assert digest.category("ctis", {}) == "trial"
    assert digest.category("pubmed", {}) == "paper"
    assert digest.category("europemc", {}) == "paper"
    assert digest.category("europemc", {"preprint": True}) == "preprint"
    assert digest.category("reporter", {}) == "grant"
    assert digest.category("cordis", {}) == "grant"
    assert digest.category("gtr", {}) == "grant"
    # Anything left (the RSS feeds) is media echo.
    assert digest.category("longevitytech", {}) == "news"


def test_editorial_date_falls_back_through_the_registry_fields():
    assert digest.editorial_date(date(2026, 11, 5), {}) == date(2026, 11, 5)
    # A trial registry record: published column empty, its own update date.
    assert digest.editorial_date(None, {"last_update": "2026-11-04"}) \
        == date(2026, 11, 4)
    assert digest.editorial_date(None, {"registration_date": "2026-10-28"}) \
        == date(2026, 10, 28)
    # EU CTIS dates are DD/MM/YYYY.
    assert digest.editorial_date(None, {"decision_date": "15/11/2026"}) \
        == date(2026, 11, 15)
    # Curated snapshot rows have no dates at all — never digested.
    assert digest.editorial_date(None, {"compound": "metformin"}) is None
    assert digest.editorial_date(None, {"last_update": "nonsense"}) is None


def test_week_slug_is_iso_monday_based():
    # 2026-11-02 is the Monday of ISO week 45; Sunday Nov 8 is the same week.
    assert digest.week_slug(date(2026, 11, 2)) == "2026-w45"
    assert digest.week_slug(date(2026, 11, 8)) == "2026-w45"
    assert digest.week_slug(date(2026, 11, 9)) == "2026-w46"


def test_rank_key_follows_the_editorial_order():
    records = [
        {"category": "news", "terms": ["aging"], "day": date(2026, 11, 5),
         "slug": "a-news"},
        {"category": "trial", "terms": ["aging"], "day": date(2026, 11, 3),
         "slug": "b-trial"},
        {"category": "paper", "terms": ["aging", "senescence", "mTOR"],
         "day": date(2026, 11, 4), "slug": "c-paper-strong"},
        {"category": "paper", "terms": ["aging"], "day": date(2026, 11, 6),
         "slug": "d-paper-weak"},
        {"category": "grant", "terms": ["aging"], "day": date(2026, 11, 5),
         "slug": "e-grant"},
    ]
    ranked = sorted(records, key=digest.rank_key)
    assert [r["slug"] for r in ranked] == [
        "b-trial", "c-paper-strong", "d-paper-weak", "e-grant", "a-news",
    ]


def test_rank_key_newer_first_within_a_group():
    older = {"category": "paper", "terms": ["aging"],
             "day": date(2026, 11, 2), "slug": "z-old"}
    newer = {"category": "paper", "terms": ["aging"],
             "day": date(2026, 11, 7), "slug": "a-new"}
    assert digest.rank_key(newer) < digest.rank_key(older)


# --- store round-trip ----------------------------------------------------------

pytestmark_db = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="needs DATABASE_URL"
)


@pytest.fixture(scope="module")
def _scratch_dsn():
    """A throwaway database — never the one DATABASE_URL points at."""
    from dontdie import store
    base = os.environ["DATABASE_URL"]
    admin = store.connect(base)
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute("DROP DATABASE IF EXISTS dontdie_digest_test")
            cur.execute("CREATE DATABASE dontdie_digest_test")
    finally:
        admin.close()
    yield base.rsplit("/", 1)[0] + "/dontdie_digest_test"
    cleanup = store.connect(base)
    cleanup.autocommit = True
    try:
        with cleanup.cursor() as cur:
            cur.execute("DROP DATABASE dontdie_digest_test")
    finally:
        cleanup.close()


WEEK_MONDAY = date(2026, 11, 2)  # ISO week 45, Mon Nov 2 – Sun Nov 8


@pytestmark_db
def test_build_creates_ranked_issues_idempotently(_scratch_dsn):
    from dontdie import store

    dsn = _scratch_dsn
    store.migrate(dsn)
    conn = store.connect(dsn)
    try:
        with conn, conn.cursor() as cur:
            cur.execute("DELETE FROM digest_items")
            cur.execute("DELETE FROM digests")
            cur.execute("DELETE FROM item_domains")
            cur.execute("DELETE FROM items")
            for slug in ("pubmed", "ctgov", "europemc", "gtr",
                         "longevitytech", "anage"):
                cur.execute(
                    "INSERT INTO sources (slug, name, url, tier)"
                    " VALUES (%s, %s, %s, %s) ON CONFLICT (slug) DO NOTHING",
                    (slug, slug, "", 1),
                )

            # (source, source_id, title, published, raw, relevant, retracted)
            seed = [
                ("ctgov", "NCT-1", "Trial moved",
                 None, {"last_update": "2026-11-06"}, True, False),
                ("pubmed", "1", "Strong paper", date(2026, 11, 5),
                 {"abstract": "aging senescence mTOR"}, True, False),
                ("gtr", "BB/1", "New UK grant", date(2026, 11, 7),
                 {"institution": "Imperial"}, True, False),
                ("europemc", "PPR-1", "Preprint", date(2026, 11, 3),
                 {"preprint": True}, True, False),
                ("longevitytech", "n1", "News item", date(2026, 11, 4),
                 {"outlet": "Longevity.Technology"}, True, False),
                # Excluded: retracted, irrelevant, undated, before the first
                # fetch, and after the current week respectively.
                ("pubmed", "2", "Retracted paper", date(2026, 11, 5),
                 {}, True, True),
                ("pubmed", "3", "Irrelevant paper", date(2026, 11, 5),
                 {}, False, False),
                ("anage", "a1", "Bowhead whale", None,
                 {"max_longevity_years": "211"}, True, False),
                ("pubmed", "4", "Before the pipeline existed",
                 date(2014, 10, 22), {}, True, False),
                ("gtr", "BB/2", "Future grant", date(2028, 1, 5),
                 {}, True, False),
            ]
            for source, source_id, title, published, raw, relevant, retracted \
                    in seed:
                cur.execute(
                    """
                    INSERT INTO items
                        (source, source_id, slug, url, title, published, raw,
                         fetched_at, is_relevant, relevance_terms,
                         relevance_method, is_retracted)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (source, source_id, f"{source}-{source_id}", "", title,
                     published, json.dumps(raw),
                     # The pipeline has existed since the seeded week.
                     WEEK_MONDAY,
                     relevant, json.dumps(["aging"]), "keyword-v1.2", retracted),
                )
                item_id = cur.fetchone()[0]
                # Tier-2 news carries no domain row — the issue must give it
                # the "coverage" section, not drop it.
                if source != "longevitytech":
                    cur.execute(
                        "INSERT INTO item_domains (item_id, domain)"
                        " VALUES (%s, %s)",
                        (item_id, "geroscience"),
                    )
    finally:
        conn.close()

    stats = digest.build(dsn)
    assert stats["issues"] == 1
    assert stats["latest_slug"] == "2026-w45"
    assert stats["latest_items"] == 5

    conn = store.connect(dsn)
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT i.source, di.rank, d.stats
                FROM digest_items di
                JOIN items i ON i.id = di.item_id
                JOIN digests d ON d.id = di.digest_id
                WHERE d.slug = '2026-w45'
                ORDER BY di.rank
                """
            )
            rows = cur.fetchall()
            assert [r[0] for r in rows] == \
                ["ctgov", "pubmed", "gtr", "europemc", "longevitytech"]
            assert [r[1] for r in rows] == [1, 2, 3, 4, 5]
            stats_json = rows[0][2]
            assert stats_json["items"] == 5
            assert stats_json["trials"] == 1
            assert stats_json["papers"] == 1
            assert stats_json["grants"] == 1
            assert stats_json["preprints"] == 1
            assert stats_json["news"] == 1
            assert stats_json["sections"] == {"geroscience": 4, "coverage": 1}

            # Idempotent: a rebuild changes nothing.
            again = digest.build(dsn)
            assert again == stats
            cur.execute("SELECT count(*) FROM digest_items")
            assert cur.fetchone()[0] == 5
            cur.execute("SELECT count(*) FROM digests")
            assert cur.fetchone()[0] == 1
    finally:
        conn.close()
