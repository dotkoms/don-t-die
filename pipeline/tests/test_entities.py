"""Entity pages (M4): the curated vocabulary, matching, and the store
round-trip."""

import json
import os

import pytest

from dontdie import entities
from dontdie.entities import (
    _name_index, _ngrams, _norm, _org_display, _org_slug, _TRIAL_ID_RE,
)
from collections import Counter


# --- pure functions -----------------------------------------------------------

def test_compound_slugs_are_unique():
    slugs = [c[0] for c in entities.COMPOUNDS]
    assert len(slugs) == len(set(slugs))


def test_name_index_covers_names_and_aliases_case_insensitively():
    index = _name_index()
    # The display name, its lowercase, and an alias all resolve.
    assert index["rapamycin"][0] == "rapamycin"
    assert index["sirolimus"][0] == "rapamycin"
    assert index["17α-estradiol"][0] == "17alpha-estradiol"
    assert index["17alpha-estradiol"][0] == "17alpha-estradiol"


def test_ngrams_fold_hyphens_and_strip_punctuation():
    grams = _ngrams("(Rapamycin) extends mouse lifespan—dosed via Sirolimus.")
    assert "rapamycin" in grams
    assert "sirolimus" in grams
    # Multi-word names match across a typographic dash boundary.
    assert "nicotinamide riboside" not in grams  # not in this text
    grams2 = _ngrams("Nicotinamide riboside supplementation")
    assert "nicotinamide riboside" in grams2


def test_org_slug_collapses_variants():
    assert _org_slug("MAYO CLINIC") == _org_slug("Mayo Clinic")
    assert _org_slug("  Mayo   Clinic ") == "mayo-clinic"
    assert _org_slug("University of California, San Francisco") \
        == "university-of-california-san-francisco"


def test_org_display_prefers_proper_case_with_deterministic_ties():
    # A sponsor's title case beats the registry's ALL CAPS at any frequency.
    assert _org_display(Counter({"MAYO CLINIC": 5, "Mayo Clinic": 1})) \
        == "Mayo Clinic"
    # All-caps pool only: most frequent, ties broken lexicographically.
    assert _org_display(Counter({"IMPERIAL": 3, "UCL": 3})) == "IMPERIAL"


def test_trial_id_regex_matches_the_three_registry_formats():
    text = ("See NCT04006321, ISRCTN12345678 and 2022-501073-40-00 "
            "but not NCT04006 (too short) or 22-501073-40-00.")
    assert set(_TRIAL_ID_RE.findall(text)) == \
        {"NCT04006321", "ISRCTN12345678", "2022-501073-40-00"}


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
            cur.execute("DROP DATABASE IF EXISTS dontdie_entities_test")
            cur.execute("CREATE DATABASE dontdie_entities_test")
    finally:
        admin.close()
    yield base.rsplit("/", 1)[0] + "/dontdie_entities_test"
    cleanup = store.connect(base)
    cleanup.autocommit = True
    try:
        with cleanup.cursor() as cur:
            cur.execute("DROP DATABASE dontdie_entities_test")
    finally:
        cleanup.close()


@pytestmark_db
def test_build_links_entities_idempotently(_scratch_dsn):
    from dontdie import store

    dsn = _scratch_dsn
    store.migrate(dsn)
    conn = store.connect(dsn)
    try:
        with conn, conn.cursor() as cur:
            cur.execute("DELETE FROM item_domains")
            cur.execute("DELETE FROM items")
            for slug in ("pubmed", "drugage", "ctgov", "gtr", "reporter",
                         "anage"):
                cur.execute(
                    "INSERT INTO sources (slug, name, url, tier)"
                    " VALUES (%s, %s, %s, %s) ON CONFLICT (slug) DO NOTHING",
                    (slug, slug, "", 1),
                )

            # (source, source_id, title, raw, relevant, retracted)
            seed = [
                # A paper citing a trial AND mentioning rapamycin: two
                # entities, linked once each (mention + citation).
                ("pubmed", "1", "Rapamycin ageing trial analysis",
                 {"abstract": "We reanalysed NCT04006321; rapamycin "
                               "extends lifespan."}, True, False),
                # The trial record it cites — a trial entity, sponsored by
                # Mayo Clinic (title case).
                ("ctgov", "NCT04006321", "Rapamycin in older adults",
                 {"sponsor": "Mayo Clinic"}, True, False),
                # A DrugAge assay row: the assay link wins over a mention in
                # the title.
                ("drugage", "d1", "Rapamycin lifespan assay in mice",
                 {"compound": "Rapamycin"}, True, False),
                # A grant from the ALL-CAPS arm of the same organization.
                ("reporter", "r1", "Rapamycin biology grant",
                 {"institution": "MAYO CLINIC"}, True, False),
                # An irrelevant item mentioning rapamycin — must NOT link.
                ("pubmed", "2", "Rapamycin off-topic",
                 {"abstract": "rapamycin"}, False, False),
                # A retracted item — must NOT link either.
                ("pubmed", "3", "Rapamycin retracted",
                 {"abstract": "rapamycin"}, True, True),
                # A snapshot row with no text and no vocabulary hit: no
                # entity, no link.
                ("anage", "a1", "Bowhead whale",
                 {"max_longevity_years": "211"}, True, False),
            ]
            for source, source_id, title, raw, relevant, retracted in seed:
                cur.execute(
                    """
                    INSERT INTO items
                        (source, source_id, slug, url, title, raw,
                         fetched_at, is_relevant, relevance_terms,
                         relevance_method, is_retracted)
                    VALUES (%s, %s, %s, %s, %s, %s, now(), %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (source, source_id, f"{source}-{source_id}", "", title,
                     json.dumps(raw), relevant, json.dumps(["aging"]),
                     "keyword-v1.2", retracted),
                )
    finally:
        conn.close()

    stats = entities.build(dsn)
    assert stats["compounds"] == 1
    assert stats["orgs"] == 1
    assert stats["trials"] == 1

    conn = store.connect(dsn)
    try:
        with conn, conn.cursor() as cur:
            # The three entities with their link-kind counts.
            cur.execute(
                "SELECT kind, slug, name, data FROM entities"
                " ORDER BY kind, slug"
            )
            rows = cur.fetchall()
            assert [(r[0], r[1]) for r in rows] == [
                ("compound", "rapamycin"), ("org", "mayo-clinic"),
                ("trial", "nct04006321"),
            ]
            compound, org, trial = rows
            assert compound[2] == "Rapamycin"
            assert compound[3]["family"] == "mTOR inhibitor"
            assert compound[3]["items"] == 4
            assert compound[3]["assay"] == 1
            assert compound[3]["mention"] == 3
            # ALL-CAPS grant merged with the title-case sponsor, and the
            # display name prefers the properly-cased variant.
            assert org[2] == "Mayo Clinic"
            assert org[3]["items"] == 2
            assert org[3]["funding"] == 1
            assert org[3]["sponsor"] == 1
            assert trial[2] == "Rapamycin in older adults"
            assert trial[3]["registry"] == "ctgov"
            assert trial[3]["registry_id"] == "NCT04006321"
            assert trial[3]["record_slug"] == "ctgov-NCT04006321"
            assert trial[3]["record"] == 1
            assert trial[3]["citation"] == 1

            # 4 compound links + 2 org links + 2 trial links = 8, and the
            # irrelevant/retracted items are absent from all of them.
            cur.execute("SELECT count(*) FROM item_entities")
            assert cur.fetchone()[0] == 8
            cur.execute(
                """
                SELECT count(*) FROM item_entities ie
                JOIN items i ON i.id = ie.item_id
                WHERE NOT i.is_relevant OR i.is_retracted
                """
            )
            assert cur.fetchone()[0] == 0

            # Idempotent: a rebuild changes nothing.
            again = entities.build(dsn)
            assert again == stats
            cur.execute("SELECT count(*) FROM entities")
            assert cur.fetchone()[0] == 3
            cur.execute("SELECT count(*) FROM item_entities")
            assert cur.fetchone()[0] == 8
    finally:
        conn.close()
