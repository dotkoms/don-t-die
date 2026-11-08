from dontdie.landing import append_fetch_log, land_item
from dontdie.sources.ctgov import parse_studies


def test_parse_studies_full_record(ctgov_payload):
    records = parse_studies(ctgov_payload)
    assert len(records) == 2

    r = records[0]
    assert r["item_id"] == "NCT06123456"
    assert r["title"] == "Rapamycin for Biological Aging"
    assert r["status"] == "RECRUITING"
    assert r["phases"] == ["PHASE2"]
    assert r["enrollment"] == 120
    assert r["sponsor"] == "Example University"
    assert r["conditions"] == ["Biological Aging"]
    assert r["interventions"] == ["Rapamycin", "Placebo"]
    assert r["start_date"] == "2026-09-01"
    assert r["completion_date"] == "2027-09-01"
    assert r["last_update"] == "2026-11-01"
    assert r["url"] == "https://clinicaltrials.gov/study/NCT06123456"
    assert "rapamycin" in r["brief_summary"]


def test_parse_studies_minimal_record_has_defaults(ctgov_payload):
    r = parse_studies(ctgov_payload)[1]
    assert r["item_id"] == "NCT06000099"
    assert r["status"] == "COMPLETED"
    assert r["phases"] == []
    assert r["start_date"] == ""
    assert r["brief_summary"] == ""


def test_land_item_is_dedupe_and_atomic(landing_dir):
    record = {"title": "T", "payload": {"raw": True}}
    p1 = land_item("pubmed", "40123456", record)
    p2 = land_item("pubmed", "40123456", {"title": "T2", "payload": {"raw": 2}})

    assert p1 == p2  # same path — the landing zone IS the dedupe
    assert not landing_dir.joinpath("pubmed/40123456.json.tmp").exists()

    import json

    doc = json.loads(p1.read_text())
    assert doc["source"] == "pubmed"
    assert doc["item_id"] == "40123456"
    assert doc["title"] == "T2"
    assert doc["fetched_at"]


def test_fetch_log_appends(landing_dir):
    append_fetch_log({"command": "fetch", "runs": {}})
    append_fetch_log({"command": "fetch", "runs": {"pubmed": {"total": 1}}})

    lines = landing_dir.parent.joinpath("fetch_log.jsonl").read_text().strip().split("\n")
    assert len(lines) == 2
