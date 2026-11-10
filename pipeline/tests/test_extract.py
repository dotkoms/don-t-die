"""Extraction pass (M5): prompt, parse, validation, cost math, and the store
round-trip with a stub client — no anthropic import, no key, no spend."""

import json
import os

import pytest

from dontdie import extract
from dontdie.extract import (
    _parse_payload, estimate_cost, item_text, user_message, validate,
)

GOOD = {
    "summary": "Rapamycin extended lifespan in old mice.",
    "evidence": "Animal",
    "interventions": ["rapamycin"],
    "outcome": "median lifespan",
}


# --- pure functions -----------------------------------------------------------

def test_system_prompt_names_all_four_fields_and_the_enum():
    for field in ("summary", "evidence", "interventions", "outcome"):
        assert f'"{field}"' in extract.SYSTEM_PROMPT
    for level in extract.EVIDENCE_LEVELS:
        assert f'"{level}"' in extract.SYSTEM_PROMPT


def test_item_text_joins_and_caps():
    text = item_text("Title", {"abstract": "abs", "brief_summary": "brief",
                               "summary": "sum"})
    assert text == "Title\n\nabs\n\nbrief\n\nsum"
    long = item_text(None, {"abstract": "x" * 20000})
    assert len(long) == extract.TEXT_CHAR_CAP


def test_user_message_carries_source_title_and_text():
    msg = user_message("pubmed", "T", "B")
    assert msg == "Source: pubmed\nTitle: T\n\nB"


def test_parse_payload_valid_fenced_and_wrapped():
    assert _parse_payload(json.dumps(GOOD)) == GOOD
    fenced = "```json\n" + json.dumps(GOOD) + "\n```"
    assert _parse_payload(fenced) == GOOD
    wrapped = "Here you go:\n" + json.dumps(GOOD) + "\nHope that helps."
    assert _parse_payload(wrapped) == GOOD
    assert _parse_payload("no json here") is None
    assert _parse_payload('{"truncated": ') is None
    assert _parse_payload('["a list"]') is None


def test_validate_enforces_the_evidence_enum():
    cleaned = validate(GOOD)
    assert cleaned is not None
    assert cleaned["evidence"] == "animal"  # normalized to lowercase
    assert cleaned["summary"] == GOOD["summary"]

    bad = dict(GOOD, evidence="superhuman")
    assert validate(bad) is None
    assert validate(dict(GOOD, summary="   ")) is None
    assert validate(dict(GOOD, outcome="")) is None
    assert validate("not a dict") is None
    assert validate(dict(GOOD, interventions="rapamycin")) is None

    # interventions: missing → [], capped at 5, empties dropped
    assert validate(dict(GOOD, interventions=None))["interventions"] == []
    capped = validate(dict(GOOD, interventions=[
        f"i{n}" for n in range(8)
    ]))
    assert capped["interventions"] == ["i0", "i1", "i2", "i3", "i4"]
    assert validate(dict(GOOD, interventions=["", " metformin "]))[
        "interventions"] == ["metformin"]


def test_estimate_cost_scales_with_items():
    items = [{"source": "pubmed", "title": "T", "text": "x" * 4000}]
    one = estimate_cost(items)
    two = estimate_cost(items + items)
    assert one["realtime"] > 0
    assert two["realtime"] == pytest.approx(
        2 * one["realtime"], abs=0.001
    )
    assert two["batch"] == pytest.approx(two["realtime"] / 2, abs=0.001)
    assert one["output_tokens"] == extract.MAX_TOKENS


# --- store round-trip ----------------------------------------------------------

pytestmark_db = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="needs DATABASE_URL"
)


class StubBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class StubMessage:
    def __init__(self, payload):
        self.content = [StubBlock(payload)]


class StubClient:
    """Duck-typed Anthropic client. Raises if called without payloads set
    (so a dry run making zero calls is proven by not exploding)."""

    def __init__(self, payloads):
        self._payloads = list(payloads)
        self.messages = self  # client.messages.create(...)
        self.calls = 0

    def create(self, **kwargs):
        assert "temperature" not in kwargs  # SDK rejects it now
        self.calls += 1
        if not self._payloads:
            raise AssertionError("stub client called with no payload queued")
        text = json.dumps(self._payloads.pop(0))
        if self.calls % 3 == 0:
            text = "```json\n" + text + "\n```"  # exercise fence tolerance
        return StubMessage(text)


class StubBatchResult:
    def __init__(self, custom_id, payload=None, failed=False):
        self.custom_id = custom_id
        self.result = self
        if failed:
            self.type = "errored"
        else:
            self.type = "succeeded"
            self.message = StubMessage(json.dumps(payload))


class StubBatchInfo:
    def __init__(self, status, results):
        self.processing_status = status
        self.model = extract.MODEL
        self._results = results

    def __iter__(self):
        return iter(self._results)


class StubBatchClient:
    def __init__(self, status, results):
        self._info = StubBatchInfo(status, results)
        self.messages = self
        self.batches = self

    def retrieve(self, batch_id):
        return self._info

    def results(self, batch_id):
        return iter(self._info._results)


@pytest.fixture(scope="module")
def _scratch_dsn():
    """A throwaway database — never the one DATABASE_URL points at."""
    from dontdie import store
    base = os.environ["DATABASE_URL"]
    admin = store.connect(base)
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute("DROP DATABASE IF EXISTS dontdie_extract_test")
            cur.execute("CREATE DATABASE dontdie_extract_test")
    finally:
        admin.close()
    yield base.rsplit("/", 1)[0] + "/dontdie_extract_test"
    cleanup = store.connect(base)
    cleanup.autocommit = True
    try:
        with cleanup.cursor() as cur:
            cur.execute("DROP DATABASE dontdie_extract_test")
    finally:
        cleanup.close()


@pytest.fixture(scope="module")
def _seeded_dsn(_scratch_dsn):
    from dontdie import store

    dsn = _scratch_dsn
    store.migrate(dsn)
    conn = store.connect(dsn)
    try:
        with conn, conn.cursor() as cur:
            cur.execute("DELETE FROM extractions")
            cur.execute("DELETE FROM items")
            cur.execute(
                "INSERT INTO sources (slug, name, url, tier)"
                " VALUES ('pubmed', 'pubmed', '', 1)"
            )
            # (source_id, title, raw, relevant, retracted)
            seed = [
                ("1", "Rapamycin in mice",
                 {"abstract": "Rapamycin extended mouse lifespan."},
                 True, False),
                ("2", "Metformin review",
                 {"abstract": "Metformin and aging, reviewed."},
                 True, False),
                ("3", "Irrelevant", {"abstract": "dental composites"},
                 False, False),
                ("4", "Rettracted rapamycin paper",
                 {"abstract": "Rapamycin, retracted."},
                 True, True),
            ]
            for source_id, title, raw, relevant, retracted in seed:
                cur.execute(
                    """
                    INSERT INTO items
                        (source, source_id, slug, url, title, raw,
                         fetched_at, is_relevant, relevance_terms,
                         relevance_method, is_retracted)
                    VALUES ('pubmed', %s, %s, '', %s, %s, now(), %s, %s,
                            'keyword-v1.2', %s)
                    """,
                    (source_id, f"pubmed-{source_id}", title,
                     json.dumps(raw), relevant, json.dumps(["aging"]),
                     retracted),
                )
    finally:
        conn.close()
    return dsn


@pytestmark_db
def test_dry_run_spends_nothing(_seeded_dsn):
    client = StubClient([])  # would raise if called
    stats = extract.run(dsn=_seeded_dsn, client=client, model=extract.MODEL)
    assert stats["go"] is False
    assert stats["pending"] == 2          # irrelevant + retracted excluded
    assert stats["already"] == 0
    assert stats["realtime"] > 0
    assert stats["batch"] == pytest.approx(stats["realtime"] / 2, abs=0.001)
    assert stats["sample_prompt"].startswith("Source: pubmed")
    assert client.calls == 0


@pytestmark_db
def test_realtime_extracts_idempotently(_seeded_dsn):
    payloads = [GOOD, dict(GOOD, evidence="human",
                           interventions=["metformin"])]
    client = StubClient(payloads)
    stats = extract.run(go=True, dsn=_seeded_dsn, client=client,
                        model=extract.MODEL)
    assert stats["extracted"] == 2
    assert stats["failed"] == 0
    assert stats["fields"] == 8
    assert client.calls == 2

    from dontdie import store
    conn = store.connect(_seeded_dsn)
    try:
        with conn, conn.cursor() as cur:
            # 2 items × 4 fields, labeled with the model.
            cur.execute(
                "SELECT count(*) FROM extractions WHERE model = %s",
                (extract.MODEL,),
            )
            assert cur.fetchone()[0] == 8
            cur.execute(
                "SELECT value FROM extractions"
                " WHERE field = 'evidence' ORDER BY item_id"
            )
            # jsonb comes back already decoded by psycopg2.
            assert [r[0] for r in cur.fetchall()] == ["animal", "human"]
    finally:
        conn.close()

    # Re-run: nothing pending at this model, zero API calls.
    again = extract.run(go=True, dsn=_seeded_dsn, client=StubClient([]),
                        model=extract.MODEL)
    assert again["extracted"] == 0
    assert again["items"] == 0

    # A model bump re-extracts everything (a new model's rows are pending).
    queue = extract.pending(_seeded_dsn, "some-other-model")
    assert len(queue["items"]) == 2


@pytestmark_db
def test_failed_items_stay_pending(_seeded_dsn):
    from dontdie import store
    conn = store.connect(_seeded_dsn)
    try:
        with conn, conn.cursor() as cur:
            cur.execute("DELETE FROM extractions")
    finally:
        conn.close()

    client = StubClient([GOOD, {"summary": "no evidence level"}])
    stats = extract.run(go=True, dsn=_seeded_dsn, client=client,
                        model=extract.MODEL)
    assert stats["extracted"] == 1
    assert stats["failed"] == 1
    # The invalid response left the item pending for the next run.
    queue = extract.pending(_seeded_dsn, extract.MODEL)
    assert len(queue["items"]) == 1


@pytestmark_db
def test_collect_stores_batch_results(_seeded_dsn):
    from dontdie import store
    conn = store.connect(_seeded_dsn)
    try:
        with conn, conn.cursor() as cur:
            cur.execute("DELETE FROM extractions")
    finally:
        conn.close()

    # Not ended yet: honest pending report, nothing stored.
    inflight = StubBatchClient("in_progress", [])
    assert extract.collect("batch-1", client=inflight,
                          dsn=_seeded_dsn)["pending"] is True

    results = [
        StubBatchResult("1", GOOD),
        StubBatchResult("2", dict(GOOD, evidence="human",
                                  interventions=["metformin"])),
        StubBatchResult("3", failed=True),  # batch-level failure: skipped
    ]
    done = StubBatchClient("ended", results)
    stats = extract.collect("batch-1", client=done, dsn=_seeded_dsn)
    assert stats["stored"] == 2
    assert stats["failed"] == 1

    conn = store.connect(_seeded_dsn)
    try:
        with conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM extractions")
            assert cur.fetchone()[0] == 8
    finally:
        conn.close()
