import datetime

from dontdie.sources import europemc


def _payload(results):
    return {"hitCount": len(results), "resultList": {"result": results}}


PPR_HIT = {
    "source": "PPR",
    "id": "PPR123456",
    "title": "Semaglutide and vascular aging",
    "doi": "10.1101/2026.11.01.123456",
    "authorString": "Wei X, Cao F, Zhang L.",
    "journalTitle": "",
    "firstPublicationDate": "2026-11-02T00:00:00Z",
    "abstractText": "GLP-1 receptor agonist and longevity pathways.",
}

PMC_HIT = {
    "source": "PMC",
    "id": "PMC9998887",
    "title": "Humanin and mitochondrial aging",
    "doi": "10.1234/example",
    "authorString": "Doe J",
    "journalTitle": "Some Open Journal",
    "firstPublicationDate": "2026-11-01",
    "abstractText": "",
}


def test_build_query_has_source_filter_and_window():
    query = europemc.build_query('"BPC-157"', days=7)
    assert "SRC:PPR" in query
    assert "SRC:PMC AND NOT (PMID:*)" in query
    assert '"BPC-157"' in query
    cutoff = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    assert f"FIRST_PDATE:[{cutoff} TO" in query


def test_parse_records_preprint_fields():
    records = europemc.parse_records(_payload([PPR_HIT]), cutoff="2026-11-01")
    assert len(records) == 1
    rec = records[0]
    assert rec["item_id"] == "PPR-PPR123456"
    assert rec["preprint"] is True
    # no journalTitle on the record: fall back to the DOI prefix label
    assert rec["journal"] == "bioRxiv/medRxiv"
    assert rec["preprint_server"] == "bioRxiv/medRxiv"
    assert rec["url"] == "https://doi.org/10.1101/2026.11.01.123456"
    assert rec["published"] == "2026-11-02"
    assert rec["authors"] == ["Wei X", "Cao F", "Zhang L"]


def test_parse_records_non_medline_pmc():
    records = europemc.parse_records(_payload([PMC_HIT]), cutoff="2026-11-01")
    rec = records[0]
    assert rec["item_id"] == "PMC-PMC9998887"
    assert rec["preprint"] is False
    assert rec["preprint_server"] == ""
    assert rec["journal"] == "Some Open Journal"


def test_parse_records_window_filters_dated_only():
    old = dict(PPR_HIT, firstPublicationDate="2026-01-01")
    undated = dict(PPR_HIT, id="PPR777", firstPublicationDate="")
    records = europemc.parse_records(
        _payload([old, undated]), cutoff="2026-11-01")
    assert [r["item_id"] for r in records] == ["PPR-PPR777"]


def test_parse_records_skips_rows_without_ids():
    assert europemc.parse_records(_payload([{"title": "orphan"}]), "2000-01-01") == []
