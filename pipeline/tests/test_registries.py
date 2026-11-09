from dontdie.sources import ctis, isrctn


# --- ISRCTN ---------------------------------------------------------------

NS = "http://www.67bricks.com/isrctn"

SEARCH_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<resultSet xmlns="{NS}" totalCount="3">
  <trial lastUpdated="2026-11-04T09:25:11.918Z">
    <isrctn>12345678</isrctn>
  </trial>
  <trial lastUpdated="2026-01-02T08:00:00.000Z">
    <isrctn>87654321</isrctn>
  </trial>
  <trial lastUpdated="">
    <isrctn>11112222</isrctn>
  </trial>
</resultSet>
"""

WHO_XML = """<?xml version="1.0" encoding="UTF-8"?>
<resultSet xmlns="http://www.67bricks.com/isrctn">
  <trial>
    <main>
      <trial_id>ISRCTN12345678</trial_id>
      <isrctn>12345678</isrctn>
      <public_title>Semaglutide in older adults</public_title>
      <scientific_title>Semaglutide for age-related muscle loss</scientific_title>
      <url>https://www.isrctn.com/ISRCTN12345678</url>
      <recruitment_status>Recruiting</recruitment_status>
      <phase>Phase 2</phase>
      <target_size>120</target_size>
      <primary_sponsor>Example University</primary_sponsor>
      <study_type>Interventional</study_type>
      <study_design>Randomised</study_design>
      <hc_freetext>Sarcopenia, aging</hc_freetext>
      <i_freetext>Drug: semaglutide</i_freetext>
      <date_registration>04/11/2026</date_registration>
      <date_enrolment>10/12/2026</date_enrolment>
    </main>
  </trial>
</resultSet>
"""


def test_isrctn_parse_search_namespaced_xml():
    total, entries = isrctn.parse_search(SEARCH_XML)
    assert total == 3
    assert [e["id"] for e in entries] == ["12345678", "87654321", "11112222"]


def test_isrctn_in_window_keeps_undated():
    assert isrctn.in_window({"id": "a", "last_updated": "2026-11-04T09Z"},
                            "2026-11-01") is True
    assert isrctn.in_window({"id": "b", "last_updated": "2026-01-02T08Z"},
                            "2026-11-01") is False
    assert isrctn.in_window({"id": "c", "last_updated": ""},
                            "2026-11-01") is True


def test_isrctn_parse_who_trial():
    record = isrctn.parse_who_trial(WHO_XML)
    assert record["item_id"] == "ISRCTN12345678"
    assert record["title"] == "Semaglutide in older adults"
    assert record["official_title"] == "Semaglutide for age-related muscle loss"
    assert record["status"] == "Recruiting"
    assert record["phases"] == ["Phase 2"]
    assert record["enrollment"] == "120"
    assert record["sponsor"] == "Example University"
    assert record["conditions"] == "Sarcopenia, aging"
    assert record["interventions"] == "Drug: semaglutide"
    # day-first dates convert to ISO
    assert record["registration_date"] == "2026-11-04"
    assert record["start_date"] == "2026-12-10"
    assert "Sarcopenia" in record["abstract"] and "semaglutide" in record["abstract"]


def test_isrctn_phase_not_applicable():
    xml = WHO_XML.replace("<phase>Phase 2</phase>",
                          "<phase>Not Applicable</phase>")
    assert isrctn.parse_who_trial(xml)["phases"] == []


def test_isrctn_parse_who_trial_requires_main():
    assert isrctn.parse_who_trial("<resultSet/>") is None


# --- CTIS -----------------------------------------------------------------

CTIS_HIT = {
    "ctNumber": "2026-512345-67-89",
    "ctTitle": "Rapamycin for immunosenescence",
    "lastUpdated": "03/11/2026",
    "ctStatus": 4,
    "trialPhase": "Phase I",
    "totalNumberEnrolled": 90,
    "sponsor": "Example Hospital",
    "sponsorType": "Hospital",
    "conditions": "Immunosenescence",
    "primaryEndPoint": "Change in senescent cell burden",
    "trialCountries": ["France:2", "Germany"],
    "ageGroup": "Adult and elderly",
    "gender": "Both",
    "decisionDateOverall": "20/10/2026",
}


def test_ctis_date_conversion():
    assert ctis._ddmmyyyy_to_iso("03/11/2026") == "2026-11-03"
    assert ctis._ddmmyyyy_to_iso("not a date") == ""
    assert ctis._ddmmyyyy_to_iso("") == ""


def test_ctis_status_mapping():
    assert ctis._status(4) == "Ongoing, recruiting"
    assert ctis._status("8") == "Ended"
    assert ctis._status(99) == "code 99"
    assert ctis._status(None) == ""
    assert ctis._status(True) == ""  # bool is not an int status


def test_ctis_countries_strips_site_counts():
    assert ctis._countries(["France:2", " Germany "]) == ["France", "Germany"]


def test_ctis_parse_search_record():
    payload = {"data": [CTIS_HIT]}
    records = ctis.parse_search(payload, cutoff="2026-11-01")
    assert len(records) == 1
    rec = records[0]
    assert rec["item_id"] == "2026-512345-67-89"
    assert rec["url"] == "https://euclinicaltrials.eu/trial/2026-512345-67-89"
    assert rec["status"] == "Ongoing, recruiting"
    assert rec["phases"] == ["Phase I"]
    assert rec["enrollment"] == 90
    assert rec["conditions"] == "Immunosenescence"
    assert rec["countries"] == ["France", "Germany"]
    assert rec["last_update"] == "2026-11-03"
    assert rec["decision_date"] == "2026-10-20"
    # abstract carries real descriptive fields for the gate and search
    assert "Immunosenescence" in rec["abstract"]
    assert "senescent cell burden" in rec["abstract"]


def test_ctis_parse_search_window_filter():
    old = dict(CTIS_HIT, lastUpdated="01/01/2026")
    assert ctis.parse_search({"data": [old]}, cutoff="2026-11-01") == []
    undated = dict(CTIS_HIT, lastUpdated="")
    assert len(ctis.parse_search({"data": [undated]},
                                 cutoff="2026-11-01")) == 1
