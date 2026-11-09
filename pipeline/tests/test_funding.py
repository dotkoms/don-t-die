from dontdie.sources import cordis, reporter


# --- NIH RePORTER ---------------------------------------------------------

HIT = {
    "appl_id": 112345678,
    "project_num": "5R01AG098765-04",
    "core_project_num": "R01AG098765",
    "fiscal_year": 2027,
    "project_title": "Senolytic clearance of senescent cells in aging",
    "abstract_text": "This project studies cellular senescence in aging.",
    "phr_text": "Relevance: aging biology.",
    "award_amount": "1,234,567",
    "award_type": "5",
    "agency_ic_admin": {
        "abbreviation": "NIA", "name": "National Institute on Aging",
    },
    "project_start_date": "2026-10-01T00:00:00.000Z",
    "project_end_date": "2031-08-31T00:00:00.000Z",
    "is_active": True,
    "project_detail_url": "https://reporter.nih.gov/project-details/112345678",
    "organization": {
        "org_name": "Example University",
        "org_city": "Boston",
        "org_state": "MA",
    },
    "principal_investigators": [
        {"first_name": "Jane", "last_name": "Doe"},
        {"first_name": "Rin", "last_name": "Tor"},
    ],
}


def test_reporter_parse_project():
    record = reporter.parse_project(HIT)
    assert record["item_id"] == "112345678"
    assert record["source"] == "reporter"
    assert record["url"] == HIT["project_detail_url"]
    assert record["published"] == "2026-10-01"
    assert record["award_amount"] == 1234567
    assert record["fiscal_year"] == 2027
    assert record["institution"] == "Example University"
    assert record["org_city"] == "Boston"
    assert record["pi_names"] == ["Jane Doe", "Rin Tor"]
    assert "abstract_text" not in record
    # abstract is abstract + phr, the gate's searchable text
    assert "senescence" in record["abstract"] and "aging biology" in record["abstract"]


def test_reporter_parse_project_minimal_hit():
    record = reporter.parse_project({"appl_id": 1, "project_title": "Aging"})
    assert record is not None
    assert record["url"] == "https://reporter.nih.gov/project-details/1"
    assert record["award_amount"] is None
    assert record["abstract"] == ""


def test_reporter_parse_project_requires_id_and_title():
    assert reporter.parse_project({"appl_id": 1}) is None
    assert reporter.parse_project({"project_title": "x"}) is None


def test_reporter_money_forms():
    assert reporter._money("1,234,567") == 1234567
    assert reporter._money(500000) == 500000
    assert reporter._money(None) is None
    assert reporter._money("") is None


def test_reporter_agency_forms():
    assert reporter._agency({"abbreviation": "NCI", "name": "National Cancer Institute"}) == "NCI"
    assert reporter._agency({"name": "National Institute on Aging"}) == "National Institute on Aging"
    assert reporter._agency(None) == ""


def test_reporter_fiscal_year_boundary():
    # FY N runs Oct (N-1) through Sep N, so October rolls to the next FY.
    class FixedDate(reporter.datetime.date):
        @classmethod
        def today(cls):
            return cls(2026, 11, 8)
    orig = reporter.datetime.date
    reporter.datetime.date = FixedDate
    try:
        assert reporter.fiscal_years() == [2027, 2026]
    finally:
        reporter.datetime.date = orig


def test_reporter_pagination_stops_at_meta_total(monkeypatch, tmp_path):
    """Pagination is offset-driven against meta.total — no early pages
    past the total, no offset math on missing results."""
    calls = []

    def fake_post(url, json, timeout, headers):
        calls.append(json["offset"])
        total = 2
        results = [
            HIT,
            {**HIT, "appl_id": 222, "project_title": "Another"},
        ][json["offset"]:max(json["offset"], 2)]
        return FakeResp({"meta": {"total": total}, "results": results})

    class FakeResp:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            pass

        def json(self):
            return self._payload

    import dontdie.config as config
    monkeypatch.setattr(config, "LANDING_DIR", tmp_path)
    monkeypatch.setattr(reporter.requests, "post", fake_post)
    monkeypatch.setattr(reporter.time, "sleep", lambda s: None)

    summary = reporter.fetch(limit=100, queries=[("geroscience", "aging")])
    assert calls == [0]  # total < page size → one page only
    assert summary["total"] == 2 and summary["per_query"]["geroscience"] == 2
    assert summary["errors"] == []


# --- EU CORDIS ------------------------------------------------------------

PROJECT = {
    "id": "101123456",
    "acronym": "AGEPRO",
    "title": "Ageing and proteostasis",
    "status": "CLOSED",
    "startDate": "2021-01-01",
    "endDate": "2024-12-31",
    "totalCost": "1500000",
    "ecMaxContribution": "1200000",
    "objective": "We study aging biology across Europe.",
    "teaser": "Aging proteostasis project.",
    "lastUpdateDate": "2026-10-01",
}


def test_cordis_build_query():
    q = cordis.build_query(["aging", "senolytic"])
    assert q == ('contenttype=project AND (/project/objective="aging" OR '
                 '/project/objective="senolytic")')


def test_cordis_parse_project():
    record = cordis.parse_project({"project": PROJECT})
    assert record["item_id"] == "101123456"
    assert record["source"] == "cordis"
    assert record["url"] == "https://cordis.europa.eu/project/id/101123456"
    assert record["published"] == "2021-01-01"
    assert record["acronym"] == "AGEPRO"
    assert record["total_cost"] == "1500000"
    assert record["ec_contribution"] == "1200000"
    # abstract carries objective + teaser for the gate
    assert "aging biology" in record["abstract"] and "proteostasis project" in record["abstract"]


def test_cordis_parse_requires_id_and_title():
    assert cordis.parse_project({"project": {"id": "1"}}) is None
    assert cordis.parse_project({"project": {"title": "x"}}) is None


def test_cordis_hits_normalizes_single_result_dict():
    multi = {"hits": {"hit": [{"project": PROJECT},
                             {"project": {**PROJECT, "id": "2"}}]}}
    assert len(cordis._hits(multi)) == 2
    single = {"hits": {"hit": {"project": PROJECT}}}
    assert len(cordis._hits(single)) == 1
    assert cordis._hits({}) == []


def test_cordis_fetch_paginates_and_stops(monkeypatch, tmp_path):
    """Two pages of hits, then stop on totalHits; single-dict page too."""
    pages = [
        {"result": {"header": {"totalHits": 3}},
         "hits": {"hit": [{"project": PROJECT},
                          {"project": {**PROJECT, "id": "2"}}]}},
        {"result": {"header": {"totalHits": 3}},
         "hits": {"hit": {"project": {**PROJECT, "id": "3"}}}},
    ]
    calls = []

    def fake_get(url, params, timeout, headers):
        calls.append(params["p"])
        return FakeResp(pages[params["p"] - 1])

    class FakeResp:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            pass

        def json(self):
            return self._payload

    import dontdie.config as config
    monkeypatch.setattr(config, "LANDING_DIR", tmp_path)
    monkeypatch.setattr(cordis.requests, "get", fake_get)
    monkeypatch.setattr(cordis.time, "sleep", lambda s: None)

    summary = cordis.fetch(queries=[("geroscience", ["aging"])])
    assert calls == [1, 2]
    assert summary["total"] == 3
    assert summary["errors"] == []
    assert {p.name for p in tmp_path.glob("cordis/*.json")} == {
        "101123456.json", "2.json", "3.json"}
