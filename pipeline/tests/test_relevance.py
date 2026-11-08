from dontdie.relevance import classify, tag


def _rec(title, abstract="", **kw):
    rec = {"title": title, "abstract": abstract}
    rec.update(kw)
    return rec


def test_title_aging_hits_word_boundary():
    ok, terms = classify(_rec("Brain imaging in elderly patients"))
    assert not ok  # "imaging" must not count as "aging"


def test_imaging_and_damaged_do_not_match():
    ok, _ = classify(_rec("Damaged imaging sensors in composites"))
    assert not ok


def test_senescence_stem_matches_inflections():
    ok, terms = classify(_rec("Cellular senescence in fibroblasts"))
    assert ok and "senescen" in terms


def test_materials_aging_excluded():
    ok, _ = classify(_rec("Aging of dental composites"))
    assert not ok


def test_materials_hint_but_strong_term_keeps_item():
    ok, _ = classify(_rec("Dental flossing and human longevity: a cohort study"))
    assert ok


def test_ctgov_summary_searched():
    ok, _ = classify(_rec("A trial", brief_summary="Effects on lifespan in mice"))
    assert ok


def test_no_terms():
    ok, terms = classify(_rec("Machine learning for weather prediction"))
    assert not ok and terms == []


def test_tag_adds_labeled_fields():
    tagged = tag(_rec("Rapamycin extends mouse lifespan"))
    assert tagged["is_relevant"] is True
    assert tagged["relevance_method"] == "keyword-v1"
    assert "rapamycin" in tagged["relevance_terms"]
