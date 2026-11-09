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
    assert tagged["relevance_method"] == "keyword-v1.1"
    assert "rapamycin" in tagged["relevance_terms"]


def test_peptide_compound_is_relevant():
    ok, terms = classify(_rec("BPC-157 and tendon healing in rats"))
    assert ok and "BPC-157" in terms


def test_glp1_class_is_relevant():
    ok, terms = classify(_rec("Semaglutide and tirzepatide in obesity management"))
    assert ok and "semaglutide" in terms and "tirzepatide" in terms


def test_generic_peptide_alone_is_not_relevant():
    # "antimicrobial peptide" has no longevity term — the gate says no.
    ok, _ = classify(_rec("A novel antimicrobial peptide against E. coli"))
    assert not ok


def test_humanin_word_boundary():
    ok, terms = classify(_rec("Mitochondrial-derived peptide humanin and aging"))
    assert ok and "humanin" in terms


def test_unicode_hyphen_matches():
    # PubMed abstracts use U+2011 in "glucagon‑like peptide‑1".
    ok, terms = classify(
        _rec("Role of glucagon‑like peptide‑1 receptor in aging")
    )
    assert ok and "glucagon-like peptide" in terms


def test_composite_endpoint_is_not_materials():
    ok, _ = classify(
        _rec("GLP-1 variants and a composite endpoint in older adults")
    )
    assert ok  # "composite" as statistics language must not exclude this


def test_materials_exclusion_still_works():
    ok, _ = classify(_rec("Aging of composite resin dental restorations"))
    assert not ok
