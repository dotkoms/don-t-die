from dontdie.sources import drugage


CSV_FIXTURE = """compound_name,species,strain,dosage,gender,ITP,avg_lifespan_change_percent,max_lifespan_change_percent,avg_lifespan_significance,max_lifespan_significance,pubmed_id
Rapamycin,"C. elegans",N2,14.7 uM,M,0,17.5,21.0,0.01,0.02,27889999
Metformin,M. musculus,C57BL/6,0.1% diet,F,0,,18.2,,0.03,25988999
,Missing compound should be skipped,,,,,,,,
"""


def test_parse_rows_builds_full_records():
    records = drugage.parse_rows(CSV_FIXTURE)
    assert len(records) == 2  # the blank-compound row is skipped

    rapa = records[0]
    assert rapa["item_id"] != ""
    assert rapa["title"] == (
        "Rapamycin: +17.5% lifespan change in C. elegans (N2)")
    assert rapa["url"] == "https://pubmed.ncbi.nlm.nih.gov/27889999/"
    assert rapa["published"] == ""  # assays carry no date of their own
    assert rapa["domain_query"] == "lifespan-data"
    assert rapa["avg_lifespan_change_percent"] == "+17.5%"
    assert "reused under CC BY 3.0" in rapa["summary"]

    met = records[1]
    # falls back to the max-lifespan figure when the average is empty
    assert met["title"] == (
        "Metformin: +18.2% lifespan change in M. musculus (C57BL/6)")
    assert met["avg_lifespan_change_percent"] == ""


def test_item_id_is_stable_and_field_sensitive():
    row = {
        "compound_name": "Rapamycin", "species": "C. elegans", "strain": "",
        "dosage": "14.7 uM", "gender": "M", "pubmed_id": "27889999",
        "avg_lifespan_change_percent": "17.5",
        "max_lifespan_change_percent": "21.0",
    }
    first = drugage.item_id(row)
    assert drugage.item_id(dict(row)) == first
    changed = dict(row, dosage="30 uM")
    assert drugage.item_id(changed) != first


def test_signed_percent():
    assert drugage._signed_percent("81.29") == "+81.3%"
    assert drugage._signed_percent("-12.0") == "-12.0%"
    assert drugage._signed_percent("") == ""
    assert drugage._signed_percent("not-a-number") == ""
