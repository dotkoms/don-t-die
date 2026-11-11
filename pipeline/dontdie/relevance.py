"""Deterministic relevance tagging (v1) — keywords, not ML.

The domain queries over-fetch (a "longevity" PubMed search happily returns
papers about the longevity of dental fillings), so before an item is shown it
passes a transparent keyword gate. This is deliberately naive and labeled:
`relevance_method` records which gate version made the call, and nothing here
is presented as learned or statistical — it is a visible, auditable filter.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

# (pattern, needs_word_boundary). Whole words are matched on boundaries so
# "aging" does not hit "imaging" and "aged" does not hit "damaged"; stems
# (senescen-, rejuvenat-, …) are matched as substrings so inflections work.
AGING_TERMS: List[Tuple[str, bool]] = [
    ("aging", True), ("ageing", True), ("aged", True),
    ("senescen", False), ("senolytic", False),
    ("geroscience", False), ("gerontolog", False), ("geriatric", False),
    ("longevity", False), ("lifespan", False), ("life span", True),
    ("life extension", True), ("rejuvenat", False), ("biological age", True),
    ("epigenetic clock", False), ("mTOR", False), ("metformin", False),
    ("rapamycin", False), ("autophagy", False), ("yamanaka", False),
    ("nicotinamide", False), ("NAD+", False), ("telomere", False),
    ("healthspan", False), ("health span", True),
    ("caloric restriction", True), ("calorie restriction", True),
    ("dietary restriction", True), ("age-related", True),
    ("age associated", True), ("mortality", False),
    # Peptide interventions (M2) — compounds circulating in the longevity
    # space, matched on boundaries so "humanin" never hits inside another word.
    ("BPC-157", True), ("epitalon", True), ("epithalon", True),
    ("MOTS-c", True), ("humanin", True), ("GHK-Cu", True),
    ("elamipretide", True), ("SS-31", True), ("tesamorelin", True),
    ("ipamorelin", True), ("CJC-1295", True), ("semaglutide", True),
    ("tirzepatide", True), ("GLP-1", True), ("glucagon-like peptide", True),
    # Peptide widening (M2, second pass) — thymosin/GHRP/SHLP families are
    # matched on the family stem so every member matches; klotho is core
    # geroscience as well as a peptide-therapy topic.
    ("thymosin beta", True), ("TB-500", True), ("thymosin alpha", True),
    ("GHRP", True), ("hexarelin", True), ("SHLP", True), ("AOD-9604", True),
    ("selank", True), ("semax", True), ("dihexa", True), ("noopept", True),
    ("carnosine", True), ("retatrutide", True), ("orforglipron", True),
    ("klotho", True),
    # Gate v1.3 (2026-11-11): the clinic-sweep compounds. Taurine, alpha-
    # ketoglutarate and everolimus are deliberately NOT gate terms: their
    # general literatures (energy drinks, biochemistry, oncology) carry no
    # aging vocabulary, so a bare mention would flood the corpus; their
    # aging-context papers land via the aging terms above. They are
    # entities only.
    ("sermorelin", True), ("ibutamoren", True), ("MK-677", True),
    ("5-amino-1MQ", True), ("ARA-290", True), ("cibinetide", True),
    ("FOXO4-DRI", True), ("DSIP", True), ("cagrilintide", True),
    ("mazdutide", True), ("survodutide", True),
    ("urolithin A", True), ("berberine", True), ("GlyNAC", True),
]

# Strong false-positive sources inside those terms; e.g. "aging" of materials.
# "composite resin" rather than "composite": in medical literature
# "composite endpoint/outcome" is standard statistics language, not materials.
EXCLUDE_HINTS = [
    "dental", "composite resin", "resin", "concrete", "batter", "capacitor",
    "corrosion", "paint", "coating", "adhesive", "photovoltaic", "bitumen",
    "asphalt", "weld", "solder",
]

# Aging-specific terms strong enough to keep an item even if a materials
# hint appears (aging is also a materials-science word). The peptide
# compounds are here too: no materials paper mentions semaglutide.
STRONG_TERMS = [
    "senescen", "senolytic", "geroscience", "gerontolog", "longevity",
    "lifespan", "life span", "rejuvenat", "healthspan", "geriatric",
    "epigenetic clock", "biological age", "caloric restriction",
    "calorie restriction", "dietary restriction", "life extension", "yamanaka",
    "bpc-157", "epitalon", "epithalon", "mots-c", "humanin", "ghk-cu",
    "elamipretide", "ss-31", "tesamorelin", "ipamorelin", "cjc-1295",
    "semaglutide", "tirzepatide", "glp-1", "glucagon-like peptide",
    "thymosin beta", "tb-500", "thymosin alpha", "ghrp", "hexarelin",
    "shlp", "aod-9604", "selank", "semax", "dihexa", "noopept", "carnosine",
    "retatrutide", "orforglipron", "klotho",
    # Gate v1.3 (2026-11-11) — the clinic-sweep compounds above.
    "sermorelin", "ibutamoren", "mk-677", "5-amino-1mq", "ara-290",
    "cibinetide", "foxo4-dri", "dsip", "cagrilintide", "mazdutide",
    "survodutide", "urolithin a", "berberine", "glynac",
]

_TERM_RE = [
    (re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE) if bounded
     else re.compile(re.escape(term), re.IGNORECASE), term)
    for term, bounded in AGING_TERMS
]


# Typographic hyphen/dash variants (U+2010, U+2011, U+2012, U+2013, U+2015,
# U+2212) — PubMed abstracts use U+2011 in "glucagon‑like peptide‑1", which
# must not dodge a term match meant for the ASCII spelling.
_HYPHEN_MAP = str.maketrans({
    "‐": "-", "‑": "-", "‒": "-", "–": "-",
    "―": "-", "−": "-",
})


def _search_text(record: Dict[str, Any]) -> str:
    fields = ["title", "abstract", "brief_summary", "official_title"]
    text = " ".join(record.get(f) or "" for f in fields).lower()
    return text.translate(_HYPHEN_MAP)


def classify(record: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Return (is_relevant, matched_terms) for a landing-zone record."""
    text = _search_text(record)
    matched = sorted({term for regex, term in _TERM_RE if regex.search(text)})
    if not matched:
        return False, []
    if any(hint in text for hint in EXCLUDE_HINTS) and not any(
        term.lower() in text for term in STRONG_TERMS
    ):
        return False, []
    return True, matched


def tag(record: Dict[str, Any]) -> Dict[str, Any]:
    """Return the record plus relevance fields (does not mutate)."""
    is_relevant, matched = classify(record)
    out = dict(record)
    out["is_relevant"] = is_relevant
    out["relevance_terms"] = matched
    out["relevance_method"] = "keyword-v1.3"
    return out
