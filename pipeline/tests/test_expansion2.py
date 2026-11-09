"""Decision 11 sources: UKRI GtR, GenAge, CellAge, AnAge + integrity pass."""

import csv
import io
import json
import os

import pytest

from dontdie.sources import anage, cellage, genage, gtr
from dontdie import integrity


# --- UKRI GtR ---------------------------------------------------------------

GTR_DETAIL = {
    "headerData": {"lastRefreshDate": "06 Jul 2026"},
    "projectOverview": {
        "projectComposition": {
            "project": {
                "id": "EA77CCFE-ECA3-4EBC-94CC-FCA2094E101B",
                "title": "Defining a role for mTORC1 activity",
                "status": "Active",
                "grantReference": "BB/Y001427/1",
                "grantCategory": "Research Grant",
                "abstractText": "Rapamycin and aging biology.",
                "technicalSummary": "mTOR in healthspan.",
                "fund": {
                    "valuePounds": 462081,
                    "start": 1708300800000,
                    "end": 1802908800000,
                    "funder": {"name": "BBSRC"},
                    "type": "INCOME_ACTUAL",
                },
                "researchTopics": [
                    {"text": "Ageing: chemistry/biochemistry", "percentage": 8},
                ],
            },
            "leadResearchOrganisation": {"name": "University of Bristol"},
            "principalInvestigators": [
                {"fullName": "Bernadette Carroll"},
                {"fullName": ""},
                None,
            ],
        }
    },
}


def test_gtr_parse_project():
    record = gtr.parse_project(GTR_DETAIL)
    assert record["item_id"] == "EA77CCFE-ECA3-4EBC-94CC-FCA2094E101B"
    assert record["source"] == "gtr"
    assert record["url"] == "https://gtr.ukri.org/projects?ref=BB/Y001427/1"
    assert record["published"] == "2024-02-19"  # fund start, epoch ms UTC
    assert record["agency"] == "BBSRC"
    assert record["award_amount"] == 462081
    assert record["status"] == "Active"
    assert record["is_active"] is True
    assert record["institution"] == "University of Bristol"
    assert record["pi_names"] == ["Bernadette Carroll"]
    assert record["project_end_date"] == "2027-02-18"
    assert record["research_topics"] == ["Ageing: chemistry/biochemistry"]
    # abstract is abstractText + technical summary, the gate's searchable text
    assert "aging biology" in record["abstract"] and "healthspan" in record["abstract"]


def test_gtr_parse_project_minimal():
    record = gtr.parse_project({
        "projectOverview": {"projectComposition": {
            "project": {"id": "X", "title": "Aging in mice"},
        }}
    })
    assert record is not None
    assert record["abstract"] == ""
    assert record["award_amount"] is None
    assert record["url"] == "https://gtr.ukri.org/"
    assert gtr.parse_project({"projectOverview": {}}) is None
    assert gtr.parse_project({}) is None


def test_gtr_ms_to_date_forms():
    assert gtr._ms_to_date(0) == "1970-01-01"
    assert gtr._ms_to_date(None) == ""
    assert gtr._ms_to_date("not-a-number") == ""


class _Resp:
    def __init__(self, payload=None, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload


def test_gtr_fetch_searches_then_lands_details(monkeypatch, landing_dir):
    """One search page with two hits (one duplicate id) → one detail land."""
    search_payload = {
        "facetedSearchResultBean": {
            "totalResults": 2,
            "results": [
                {"projectComposition": {"project": {
                    "id": "A", "grantReference": "BB/1",
                }}},
                {"projectComposition": {"project": {
                    "id": "A", "grantReference": "BB/1",  # duplicate id
                }}},
            ],
        }
    }
    calls = []

    def fake_get(url, params, timeout, headers):
        calls.append(url.split("/")[-1] + json.dumps(params, sort_keys=True))
        if "search" in url:
            return _Resp(search_payload)
        return _Resp(GTR_DETAIL)

    monkeypatch.setattr(gtr.requests, "get", fake_get)
    monkeypatch.setattr(gtr.time, "sleep", lambda s: None)

    summary = gtr.fetch(queries=[("geroscience", "aging")])
    assert summary["matched"] == 1
    assert summary["total"] == 1 and summary["new"] == 1
    assert summary["errors"] == []
    assert len(list(landing_dir.glob("gtr/*.json"))) == 1
    assert len(calls) == 2  # one search page + one detail


def test_gtr_get_retries_once_on_503(monkeypatch):
    responses = [_Resp(status=503), _Resp({"ok": 1})]

    def fake_get(url, params, timeout, headers):
        return responses.pop(0)

    monkeypatch.setattr(gtr.requests, "get", fake_get)
    monkeypatch.setattr(gtr.time, "sleep", lambda s: None)
    resp = gtr._get("https://x", {})
    assert resp.status_code == 200


# --- GenAge ------------------------------------------------------------------

HUMAN_CSV = (
    "GenAge ID,symbol,name,entrez gene id,uniprot,why\n"
    '6,TP53,tumor protein p53,7157,P53_HUMAN,"mammal,model,cell"\n'
    "17,KL,klotho,9365,KLOT_HUMAN,mammal\n"
)
MODELS_CSV = (
    "GenAge ID,symbol,name,organism,entrez gene id,"
    "avg lifespan change (max obsv),lifespan effect,longevity influence\n"
    "1,aak-2,AMP-Activated Kinase,Caenorhabditis elegans,181727,30,Increase,"
    "Pro-Longevity\n"
)


def test_genage_parse_human_rows():
    records = genage.parse_human_rows(HUMAN_CSV)
    assert len(records) == 2
    tp53 = records[0]
    assert tp53["item_id"] == "human-6"
    assert tp53["gene_symbol"] == "TP53"
    assert tp53["evidence"] == "mammal,model,cell"
    assert tp53["url"] == "https://www.ncbi.nlm.nih.gov/gene/7157"
    assert tp53["domain_query"] == "genetics-data"
    # the constructed title carries the gate term honestly
    assert "aging" in tp53["title"].lower()


def test_genage_parse_models_rows():
    records = genage.parse_models_rows(MODELS_CSV)
    assert len(records) == 1
    row = records[0]
    assert row["gene_symbol"] == "aak-2"
    assert row["organism"] == "Caenorhabditis elegans"
    assert row["longevity_influence"] == "Pro-Longevity"
    assert row["avg_lifespan_change_percent"] == "30"
    assert "longevity" in row["title"].lower()
    # id keyed by gene+organism so GenAge ids (reused across species) dedupe
    assert row["item_id"] == genage.parse_models_rows(MODELS_CSV)[0]["item_id"]


def test_genage_parse_skips_rows_without_ids():
    assert genage.parse_human_rows("GenAge ID,symbol,name\n,x,y\n") == []
    assert genage.parse_models_rows("symbol,organism\n,x\n") == []


# --- CellAge ------------------------------------------------------------------

CELLAGE_TSV = (
    "Entrez ID\tGene symbol\tGene name\tCancer Cell\tType of senescence\t"
    "Senescence Effect\tReference\n"
    "5243\tABCB1\tATP binding cassette subfamily B member 1\tYes\t"
    "Stress-induced\tInduces\t10825123\n"
    "368\tABCC6\tATP binding cassette subfamily C member 6\tYes\t"
    "Unclear\tInhibits\t28536638\n"
)


def test_cellage_parse_rows():
    records = cellage.parse_rows(CELLAGE_TSV)
    assert len(records) == 2
    row = records[0]
    assert row["gene_symbol"] == "ABCB1"
    assert row["senescence_effect"] == "Induces"
    assert row["pubmed_id"] == "10825123"
    assert row["url"] == "https://www.ncbi.nlm.nih.gov/gene/5243"
    assert "senescence" in row["title"].lower()
    assert row["item_id"] == cellage.item_id("5243", "ABCB1")
    assert "inhibits" in records[1]["title"].lower()


# --- AnAge --------------------------------------------------------------------

ANAGE_TSV = (
    "HAGRID\tKingdom\tPhylum\tClass\tOrder\tFamily\tGenus\tSpecies\t"
    "Common name\tAdult weight (g)\tMaximum longevity (yrs)\tSource\t"
    "Specimen origin\tSample size\tData quality\tReferences\n"
    "00003\tAnimalia\tAnnelida\tPolychaeta\tSabellida\tSiboglinidae\t"
    "Escarpia\tlaminata\tEscarpia laminata\t\t300\t652\twild\tmedium\t"
    "acceptable\t652\n"
    "00099\tAnimalia\tChordata\tMammalia\tCetacea\tBalaenidae\tBalaena\t"
    "mysticetus\tBowhead whale\t100000000\t211\t1\twild\tlarge\thigh\t1\n"
    "00100\tAnimalia\tChordata\tMammalia\tX\tX\tNo\tdata\t\t\t\t\t\t\t\t\n"
)


def test_anage_parse_rows():
    records = anage.parse_rows(ANAGE_TSV)
    # the third row has no longevity value — taxonomy-only rows are skipped
    assert len(records) == 2
    whale = records[1]
    assert whale["item_id"] == "00099"
    assert whale["species"] == "Balaena mysticetus"
    assert whale["common_name"] == "Bowhead whale"
    assert whale["max_longevity_years"] == "211"
    assert whale["data_quality"] == "high"
    assert "maximum longevity 211 years" in whale["title"]
    assert whale["domain_query"] == "lifespan-data"


# --- Retraction Watch integrity ----------------------------------------------

def _rw_csv_text():
    """A real-shaped Retraction Watch CSV (aligned by DictWriter, not by hand)."""
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=[
        "Record ID", "Title", "Subject", "Institution", "Journal", "Publisher",
        "Country", "Author", "URLS", "ArticleType", "RetractionDate",
        "RetractionDOI", "OriginalPaperDate", "OriginalPaperDOI",
        "OriginalPaperPubMedID", "RetractionNature", "Reason", "Paywalled",
        "Notes",
    ])
    writer.writeheader()
    writer.writerows([
        {
            "Record ID": "74596", "Title": "Some aging paper",
            "Subject": "GER", "Journal": "Some Journal", "Publisher": "Pub",
            "ArticleType": "Research Article",
            "RetractionDate": "7/15/2026 0:00",
            "RetractionDOI": "10.1007/s12540-026-02388-1",
            "OriginalPaperDate": "10/16/2019 0:00",
            "OriginalPaperDOI": "10.1007/S12540-019-00482-1",
            "OriginalPaperPubMedID": "27634749",
            "RetractionNature": "Retraction",
            "Reason": "Unreliable Data;Duplication of/in Image",
            "Paywalled": "No",
        },
        {
            "Record ID": "74597", "Title": "Another aging paper",
            "Subject": "GER", "Journal": "Other Journal", "Publisher": "Pub",
            "ArticleType": "Research Article",
            "RetractionDate": "1/2/2025 0:00",
            "OriginalPaperDate": "1/1/2020 0:00",
            "OriginalPaperDOI": "https://doi.org/10.1234/abc.2020.01",
            "OriginalPaperPubMedID": "0",
            "RetractionNature": "Expression of Concern",
            "Reason": "Concerns",
            "Paywalled": "No",
        },
        {
            "Record ID": "74598", "Title": "A CellAge-ish paper",
            "Subject": "GER", "Journal": "J", "Publisher": "Pub",
            "ArticleType": "Article",
            "RetractionDate": "3/3/2025 0:00",
            "OriginalPaperDate": "1/1/2021 0:00",
            "OriginalPaperPubMedID": "28536638",
            "RetractionNature": "Retraction",
            "Reason": "Fake Data",
            "Paywalled": "No",
        },
    ])
    return out.getvalue()


RW_CSV = _rw_csv_text()


def test_integrity_normalizers():
    assert integrity.normalize_doi("https://doi.org/10.1/ABC.2020") == "10.1/abc.2020"
    assert integrity.normalize_doi("doi:10.1/x.") == "10.1/x"
    assert integrity.normalize_doi(None) == ""
    assert integrity.normalize_pmid("27634749") == "27634749"
    assert integrity.normalize_pmid(0) == ""
    assert integrity.normalize_pmid("") == ""
    assert integrity.normalize_pmid("unavailable") == ""
    assert integrity.normalize_date("7/15/2026 0:00") == "2026-07-15"
    assert integrity.normalize_date("Date unknown") == ""
    assert integrity.normalize_date("") == ""


def test_integrity_parse_retractions():
    lookup = integrity.parse_retractions(RW_CSV)
    first = lookup["doi:10.1007/s12540-019-00482-1"]
    assert first["nature"] == "Retraction"
    assert first["reason"] == "Unreliable Data;Duplication of/in Image"
    assert first["date"] == "2026-07-15"
    assert first["url"] == "https://doi.org/10.1007/s12540-026-02388-1"
    # the same original paper is also reachable by its PMID
    assert lookup["pmid:27634749"] is first
    second = lookup["doi:10.1234/abc.2020.01"]
    assert second["nature"] == "Expression of Concern"
    assert second["url"] == ""  # no retraction DOI, no URLS → honest empty


def test_integrity_item_keys():
    # pubmed: source_id IS the PMID
    assert integrity._item_keys("pubmed", "27634749", {"doi": "10.1/x"}) == [
        "doi:10.1/x", "pmid:27634749",
    ]
    # drugage: pubmed_id in raw; source_id is a composite hash
    assert integrity._item_keys("drugage", "abc123", {"pubmed_id": "10825123"}) == [
        "pmid:10825123",
    ]
    # europemc: DOI only (non-Medline records carry no PMID)
    assert integrity._item_keys("europemc", "PPR-1", {"doi": "10.1101/x"}) == [
        "doi:10.1101/x",
    ]
    assert integrity._item_keys("cordis", "101", {}) == []


# --- store round-trip for the integrity flags --------------------------------

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
            cur.execute("DROP DATABASE IF EXISTS dontdie_int_test")
            cur.execute("CREATE DATABASE dontdie_int_test")
    finally:
        admin.close()
    yield base.rsplit("/", 1)[0] + "/dontdie_int_test"
    cleanup = store.connect(base)
    cleanup.autocommit = True
    try:
        with cleanup.cursor() as cur:
            cur.execute("DROP DATABASE dontdie_int_test")
    finally:
        cleanup.close()


@pytestmark_db
def test_integrity_refresh_flags_matching_items(_scratch_dsn, monkeypatch,
                                                 tmp_path):
    from dontdie import store

    dsn = _scratch_dsn
    store.migrate(dsn)
    conn = store.connect(dsn)
    try:
        with conn, conn.cursor() as cur:
            cur.execute("DELETE FROM item_domains")
            cur.execute("DELETE FROM extractions")
            cur.execute("DELETE FROM items")
            for source in ("pubmed", "europemc", "drugage"):
                cur.execute(
                    "INSERT INTO sources (slug, name, url, tier)"
                    " VALUES (%s, %s, %s, %s)"
                    " ON CONFLICT (slug) DO NOTHING",
                    (source, source, "", 1),
                )
            for source, source_id, raw in [
                ("pubmed", "27634749", {"doi": "10.1007/S12540-019-00482-1",
                                        "title": "Retracted aging paper"}),
                ("europemc", "PPR-1", {"doi": "10.1101/not-retracted",
                                       "title": "Fine preprint"}),
                ("drugage", "h1", {"pubmed_id": "28536638",
                                   "compound": "metformin"}),
            ]:
                cur.execute(
                    "INSERT INTO items (source, source_id, slug, url, title,"
                    " raw) VALUES (%s, %s, %s, %s, %s, %s)",
                    (source, source_id, f"{source}-{source_id}", "", "",
                     json.dumps(raw)),
                )
    finally:
        conn.close()

    csv_path = tmp_path / "rw.csv"
    csv_path.write_text(RW_CSV)
    monkeypatch.setattr(integrity, "LOCAL_CSV", csv_path)
    monkeypatch.setattr(integrity, "download_csv", lambda: csv_path)

    stats = integrity.refresh(dsn)
    assert stats["checked"] == 3
    # pubmed matches by DOI and PMID, drugage by its pubmed_id
    assert stats["flagged"] == 2

    conn = store.connect(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT source, source_id, is_retracted, retraction_nature,"
                " retraction_url FROM items ORDER BY source"
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    assert rows == [
        ("drugage", "h1", True, "Retraction", ""),
        ("europemc", "PPR-1", False, None, None),
        ("pubmed", "27634749", True, "Retraction",
         "https://doi.org/10.1007/s12540-026-02388-1"),
    ]
