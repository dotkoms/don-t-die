from dontdie.sources.pubmed import parse_efetch_xml, parse_esearch

FIXTURE = __file__.replace("test_pubmed.py", "fixtures/pubmed_efetch.xml")


def _load():
    with open(FIXTURE) as f:
        return f.read()


def test_parse_esearch():
    assert parse_esearch({"esearchresult": {"idlist": [1, 2, "3"]}}) == ["1", "2", "3"]
    assert parse_esearch({}) == []


def test_parse_efetch_xml_counts_and_ids():
    records = parse_efetch_xml(_load())
    assert [r["item_id"] for r in records] == ["40123456", "40123457"]
    assert all(r["source"] == "pubmed" for r in records)


def test_parse_efetch_xml_first_record_fields():
    r = parse_efetch_xml(_load())[0]
    assert r["title"] == "Rapamycin dosing in older adults: a randomized trial"
    assert r["doi"] == "10.1038/example.2026.001"
    assert r["published"] == "2026-10-15"
    assert r["journal"] == "Nat Aging"
    assert r["authors"] == ["Jane A Doe", "Aging Research Consortium"]
    assert r["url"] == "https://pubmed.ncbi.nlm.nih.gov/40123456/"
    assert "BACKGROUND: Rapamycin extends lifespan in mice." in r["abstract"]
    assert "We report a 12-week trial in 65 adults." in r["abstract"]


def test_parse_efetch_xml_medline_date_and_missing_doi():
    r = parse_efetch_xml(_load())[1]
    # MedlineDate ranges have no Year/Month/Day elements — falls back to the text.
    assert r["published"] == "2026 Sep-Oct"
    assert r["doi"] == ""
    assert r["journal"] == "Journal of Geroscience"
