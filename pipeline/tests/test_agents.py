import pytest

from dontdie.agents import outlets, research


def test_outlet_allowlist_classifies_news_and_primary():
    kind, name = outlets.verify_url(
        "https://www.longevity.technology/new-rapamycin-trial/"
    )
    assert kind == "news" and name == "Longevity.Technology"
    kind, name = outlets.verify_url("https://pubmed.ncbi.nlm.nih.gov/1234/")
    assert kind == "primary" and name == "pubmed.ncbi.nlm.nih.gov"


def test_outlet_allowlist_refuses_unknown_hosts():
    kind, name = outlets.verify_url("https://someblog.example.com/post")
    assert kind == "" and name == ""
    assert not outlets.is_verified("https://forums.example.com/t/1")


def test_verify_dedupes_canonical_urls_and_reports_refused():
    candidates = [
        {"url": "https://www.longevity.technology/a?utm_source=feed",
         "title": "A"},
        {"url": "https://longevity.technology/a", "title": "A again"},
        {"url": "https://randomblog.io/x", "title": "Refuse me"},
    ]
    kept, refused = research.verify(candidates)
    assert len(kept) == 1
    assert kept[0]["kind"] == "news"
    assert kept[0]["verified"] is True
    assert refused == ["https://randomblog.io/x"]


def test_plan_is_pure_and_honest():
    manifest = research.plan("BPC-157", model="claude-opus-5")
    assert manifest["target"] == "BPC-157"
    assert manifest["model"] == "claude-opus-5"
    assert [s["agent"] for s in manifest["steps"]] == [
        "news scout", "primary scout", "verifier", "synthesizer",
    ]
    assert "estimate" in manifest  # dry run must show cost, labeled estimate


def test_dry_run_spends_nothing_without_go(capsys):
    """Default invocation prints the plan and never touches the API."""
    status = research.run("BPC-157")
    out = capsys.readouterr().out
    assert status == 0
    assert "dry run" in out
    assert "--go" in out  # tells the operator exactly how to approve the job


def test_go_without_key_refuses_honestly(capsys, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    status = research.run("BPC-157", go=True)
    out = capsys.readouterr().out
    assert status == 2
    assert "ANTHROPIC_API_KEY" in out


def test_extract_json_array_tolerates_fences_and_prose():
    text = 'Here you go:\n```json\n[{"title": "T", "url": "https://x.com/1", "note": "n"}]\n```\nthanks'
    parsed = research._extract_json_array(text)
    assert parsed == [{"title": "T", "url": "https://x.com/1", "note": "n"}]
    assert research._extract_json_array("no json here") == []


def test_slugify():
    assert research.slugify("BPC-157 peptide!") == "bpc-157-peptide"
